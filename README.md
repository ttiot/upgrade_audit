# Audit Upgrade

Script `audit_upgrade.py` analyse les mises à jour disponibles pour les paquets Debian et génère un rapport sur les risques de breaking changes. Il peut interroger l'API OpenAI ou un serveur OpenLLM compatible pour valider la compatibilité des fichiers de configuration.

## Utilisation

Installez d'abord la dépendance requise :

```bash
pip install -r requirements.txt
```

Puis lancez le script :

```bash
python3 audit_upgrade.py --openai-key MON_API_KEY
```

Pour utiliser un serveur OpenLLM local :

```bash
python3 audit_upgrade.py --llm openllm --openllm-url http://localhost:3000/v1/chat/completions
```

Options principales :
- `--installed-file` : fichier contenant la sortie `apt list --installed`.
- `--upgradable-file` : fichier contenant la sortie `apt list --upgradable`.
- `--format {md,html}` : format du rapport.
- `--no-email` : ne pas envoyer le rapport par mail, l'enregistrer localement.
- `--llm {openai,openllm}` : choix du modèle de langage à utiliser.
- `--openllm-url` : URL complète du serveur OpenLLM.
- `--openllm-key` : clé API pour OpenLLM (optionnel).
```

Le script n'effectue aucune mise à jour; il se contente de produire un rapport.
