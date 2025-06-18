#!/usr/bin/env python3
"""Audit des mises à jour des paquets Debian.

Ce script analyse les mises à jour disponibles pour les paquets installés et
produit un rapport sur les risques potentiels de breaking changes en se basant
sur l'analyse de l'API OpenAI. Le rapport est généré en Markdown ou HTML et
peut être envoyé par mail ou enregistré localement.
"""

import argparse
import os
import subprocess
import sys
from email.mime.text import MIMEText
from typing import Dict, List, Optional

import requests

API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENLLM_URL = "http://localhost:3000/v1/chat/completions"
MODEL = "gpt-3.5-turbo"

def run_cmd(command: str) -> str:
    """Exécute une commande shell et renvoie sa sortie ou une chaîne vide."""
    try:
        result = subprocess.run(
            command, shell=True, check=False, capture_output=True, text=True
        )
        return result.stdout
    except Exception:
        return ""


def parse_apt_list(output: str) -> Dict[str, str]:
    """Parse la sortie de `apt list` et renvoie un dict {package: version}."""
    packages: Dict[str, str] = {}
    for line in output.splitlines():
        if not line or "/" not in line:
            continue
        parts = line.split()
        name = parts[0].split("/")[0]
        if len(parts) > 1:
            version = parts[1]
        else:
            version = ""
        packages[name] = version
    return packages


def load_packages_from_file(path: str) -> Dict[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return parse_apt_list(content)


def get_installed_packages(path: Optional[str]) -> Dict[str, str]:
    if path:
        return load_packages_from_file(path)
    output = run_cmd("apt list --installed 2>/dev/null")
    return parse_apt_list(output)


def get_upgradable_packages(path: Optional[str]) -> Dict[str, str]:
    if path:
        return load_packages_from_file(path)
    output = run_cmd("apt list --upgradable 2>/dev/null")
    return parse_apt_list(output)


def find_config_path(package: str) -> Optional[str]:
    """Recherche un fichier de configuration probable pour le paquet."""
    candidates = [
        f"/etc/{package}",
        f"/etc/{package}.conf",
        f"/usr/local/etc/{package}",
        f"/usr/local/etc/{package}.conf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    search_cmd = (
        f"find /etc /usr/local/etc -maxdepth 1 -name '*{package}*' 2>/dev/null"
    )
    for line in run_cmd(search_cmd).splitlines():
        if os.path.exists(line):
            return line
    return None


def load_changelog(package: str) -> str:
    """Tente de récupérer le changelog de la nouvelle version."""
    return run_cmd(f"apt-get changelog {package} 2>/dev/null")


def openai_request(prompt: str, key: str) -> str:
    headers = {"Authorization": f"Bearer {key}"}
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    try:
        resp = requests.post(API_URL, headers=headers, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"OpenAI request failed: {exc}"


def openllm_request(prompt: str, url: str, key: str) -> str:
    headers = {"Authorization": f"Bearer {key or 'local'}"}
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"OpenLLM request failed: {exc}"


def analyze_package(
    name: str,
    current: str,
    candidate: str,
    config_path: Optional[str],
    changelog: str,
    key: str,
    llm: str,
    openllm_url: str,
    openllm_key: str,
) -> Dict[str, object]:
    prompt = (
        f"Nous envisageons de mettre à jour le paquet {name} de la version {current} "
        f"vers {candidate}. Voici le changelog ou les notes de version de la nouvelle "
        f"version:\n\n{changelog}\n\n"
        "Indique s'il existe des breaking changes. Si oui, analyse la compatibilité du "
        "fichier de configuration actuel situé à l'emplacement suivant :"
        f" {config_path}. Résume en quelques lignes en français et conclus par 'safe' "
        "ou 'not safe'."
    )
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_content = f.read()
            prompt += f"\n\nConfiguration actuelle:\n```\n{config_content}\n```"
        except Exception:
            pass
    if llm == "openllm":
        print("  -> interrogation du serveur OpenLLM")
        answer = openllm_request(prompt, openllm_url, openllm_key)
    else:
        print("  -> interrogation de l'API OpenAI")
        answer = openai_request(prompt, key)
    safe = "safe" in answer.lower() and "not safe" not in answer.lower()
    breaking = "breaking" in answer.lower()
    return {
        "name": name,
        "current": current,
        "candidate": candidate,
        "config": config_path,
        "breaking": breaking,
        "safe": safe,
        "summary": answer,
    }


def generate_report(items: List[Dict[str, object]], fmt: str) -> str:
    if fmt == "html":
        lines = ["<html><body>", "<h1>Audit de mise à jour</h1>", "<table border='1'>",
                 "<tr><th>Paquet</th><th>Actuelle</th><th>Disponible" \
                 "</th><th>Breaking</th><th>Statut</th><th>Configuration" \
                 "</th><th>Analyse</th></tr>"]
        for it in items:
            lines.append(
                "<tr>"
                f"<td>{it['name']}</td>"
                f"<td>{it['current']}</td>"
                f"<td>{it['candidate']}</td>"
                f"<td>{'Oui' if it['breaking'] else 'Non'}</td>"
                f"<td>{'safe' if it['safe'] else 'not safe'}</td>"
                f"<td>{it['config'] or ''}</td>"
                f"<td>{it['summary']}</td>"
                "</tr>"
            )
        lines.extend(["</table>", "</body></html>"])
        return "\n".join(lines)
    else:
        lines = ["# Audit de mise à jour\n"]
        for it in items:
            lines.extend([
                f"## {it['name']}",
                f"- Version actuelle : {it['current']}",
                f"- Version disponible : {it['candidate']}",
                f"- Breaking change : {'Oui' if it['breaking'] else 'Non'}",
                f"- Statut : {'safe' if it['safe'] else 'not safe'}",
            ])
            if it['config']:
                lines.append(f"- Fichier de configuration : `{it['config']}`")
            lines.append(f"- Analyse : {it['summary']}\n")
        return "\n".join(lines)


def send_email(report: str, fmt: str, recipient: str) -> None:
    msg = MIMEText(report, "html" if fmt == "html" else "plain", "utf-8")
    msg["Subject"] = "Audit de mise à jour"
    msg["From"] = f"audit@{os.uname().nodename}"
    msg["To"] = recipient
    with subprocess.Popen(["/usr/sbin/sendmail", "-t", "-oi"], stdin=subprocess.PIPE) as p:
        p.communicate(msg.as_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit des mises à jour des paquets Debian")
    parser.add_argument("--installed-file", help="Fichier des paquets installés")
    parser.add_argument("--upgradable-file", help="Fichier des paquets upgradables")
    parser.add_argument("--no-email", action="store_true", help="Ne pas envoyer le rapport par mail")
    parser.add_argument("--output", default="upgrade_report.md", help="Fichier de sortie si --no-email")
    parser.add_argument("--format", choices=["md", "html"], default="md", help="Format du rapport")
    parser.add_argument("--openai-key", help="Clé API OpenAI (ou via OPENAI_API_KEY)")
    parser.add_argument("--llm", choices=["openai", "openllm"], default="openai", help="Fournisseur du LLM")
    parser.add_argument("--openllm-url", default=DEFAULT_OPENLLM_URL, help="URL du serveur OpenLLM")
    parser.add_argument("--openllm-key", help="Clé API OpenLLM (ou via OPENLLM_API_KEY)")
    parser.add_argument("--recipient", default="root", help="Destinataire du mail")
    args = parser.parse_args()

    key = args.openai_key or os.getenv("OPENAI_API_KEY")
    openllm_key = args.openllm_key or os.getenv("OPENLLM_API_KEY", "")
    if args.llm == "openai" and not key:
        print("Clé API OpenAI requise", file=sys.stderr)
        sys.exit(1)

    print("Récupération des paquets installés...")
    installed = get_installed_packages(args.installed_file)
    print(f"{len(installed)} paquets installés détectés")
    print("Récupération des paquets upgradables...")
    upgradable = get_upgradable_packages(args.upgradable_file)
    print(f"{len(upgradable)} mises à jour disponibles")

    items: List[Dict[str, object]] = []
    for pkg, candidate_version in upgradable.items():
        print(f"Analyse du paquet {pkg}...")
        current_version = installed.get(pkg, "")
        config = find_config_path(pkg)
        changelog = load_changelog(pkg)
        item = analyze_package(
            pkg,
            current_version,
            candidate_version,
            config,
            changelog,
            key,
            args.llm,
            args.openllm_url,
            openllm_key,
        )
        items.append(item)

    print("Génération du rapport...")
    report = generate_report(items, args.format)

    if args.no_email:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Rapport enregistré dans {args.output}")
    else:
        send_email(report, args.format, args.recipient)
        print("Rapport envoyé par mail")


if __name__ == "__main__":
    main()
