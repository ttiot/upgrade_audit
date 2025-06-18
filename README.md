# Audit Upgrade

Script `audit_upgrade.py` analyse les mises à jour disponibles pour les paquets Debian et génère un rapport sur les risques de breaking changes. Il interroge l'API OpenAI pour valider la compatibilité des fichiers de configuration.

## Utilisation

Installez d'abord la dépendance requise :

```bash
pip install -r requirements.txt
```

Puis lancez le script :

```bash
python3 audit_upgrade.py --openai-key MON_API_KEY
```

Options principales :
- `--installed-file` : fichier contenant la sortie `apt list --installed`.
- `--upgradable-file` : fichier contenant la sortie `apt list --upgradable`.
- `--format {md,html}` : format du rapport.
- `--no-email` : ne pas envoyer le rapport par mail, l'enregistrer localement.
```

Le script n'effectue aucune mise à jour; il se contente de produire un rapport.
