#!/bin/bash
# Double-clique sur ce fichier (ou lance « bash lancer-mac.command » dans le Terminal)
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo ""
  echo "  Python n'est pas installé. Installe-le depuis https://www.python.org/downloads/"
  echo ""
  read -p "Appuie sur Entrée pour fermer..."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "  Première installation, ça peut prendre 5 à 10 minutes..."
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
python -m pip install -q -U "yt-dlp[default]"

[ -f .env ] || cp .env.example .env

if ! command -v deno >/dev/null 2>&1; then
  echo ""
  echo "  Conseil : installe Deno pour que le téléchargement YouTube marche bien :"
  echo "     curl -fsSL https://deno.land/install.sh | sh"
  echo ""
fi

python -m app.main
