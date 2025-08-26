# <img src="https://i.imgur.com/R9kh7bC.png" width="30"/> Wawacity Stremio Addon

Addon Stremio qui cherche sur Wawacity, convertit en liens directs via AllDebrid et permet la lecture des fichiers. Toutes les qualités, langues et tailles disponibles sont retournées comme sources Stremio distinctes.

<img src="https://i.imgur.com/oDxBfB1.jpeg">

## 🗒️ Prérequis

- Python: https://www.python.org/downloads/
- Requirements: 
```
pip install -r requirements.txt
```
- Une clé API AllDebrid (⚠️ nécessité d'un compte **payant**): https://alldebrid.com/apikeys
- Un jeton d'accès API TMDB (**compte obligatoire**): https://www.themoviedb.org/settings/api

## ⚙️ Configuration

- Ouvrez le fichier `config.json` et mettez à jour l'URL permettant d'accéder à Wawacity si nécessaire, ainsi que le port du serveur web si besoin.
  - Si vous ne pouvez vous rendre sur le site de Wawacity via leur URL, [changez vos paramètres DNS](https://one.one.one.one/fr-FR/dns/).
- Démarrez l'addon:

```
python Wawacity_AD.py
```

- Accédez à la configuration de l'addon via votre navigateur à l'adresse indiquée (de base `http://localhost:7000`).
- Terminez la configuration en renseignant votre clé API AllDebrid ainsi que votre jeton d'accès API TMDB.

<img src="https://i.imgur.com/54qqqVA.png">

## 🛠️ Comment ça marche

- Stremio appelle `/{config}/stream/{type}/{imdb_id}.json`.
	- `config`: clé API AllDebrid & TMDB
	- `type`: movie
	- `imdb_id`: identifiant IMDB
- L'addon récupère le `title` et `year` via TMDB et `imdb_id`.
- L'addon lance la recherche à partir de `search.py`.
- `search.py` scrape Wawacity, ne garde que les liens 1fichier et retourne un JSON comme celui ci:

```json
{
  "title": "Mission: Impossible - The Final Reckoning",
  "year": "2025",
  "results": [
    {
      "label": "WEB-DL 4K - MULTI (TRUEFRENCH)",
      "language": "MULTI (TRUEFRENCH)",
      "quality": "WEB-DL 4K",
      "size": "31.1 Go",
      "dl_protect": "https://dl-protect.link/...",
      "original_name": "Mission : Impossible – The Final Reckoning [WEB-DL 4K] - MULTI (TRUEFRENCH)"
    },
    {
      "label": "WEBRIP 720p - TRUEFRENCH",
      "language": "TRUEFRENCH",
      "quality": "WEBRIP 720p",
      "size": "4.5 Go",
      "dl_protect": "https://dl-protect.link/...",
      "original_name": "Mission : Impossible – The Final Reckoning [WEBRIP 720p] - TRUEFRENCH"
    },
    ...
  ]
}
```

- Pour chaque résultat, l'addon crée une source Stremio
- Si une source est choisie, Stremio appelle `/resolve?link={DL_PROTECT_LINK}&apikey={ALLDEBRID_API_KEY}` qui retourne un lien direct AllDebrid streamable dans l'application.

## 🐛 Debug
- Test recherche: `http://localhost:7000/debug/test-search?title={TITLE}&year={YEAR}`
- Test AllDebrid: `http://localhost:7000/debug/test-alldebrid?link={DL_PROTECT_LINK}&apikey={ALLDEBRID_API_KEY}`

## ⚠️ Disclaimer

Cet addon fait simplement l'intermédiaire entre un site web (Wawacity) et l'utilisateur via Stremio. Il ne stocke ni ne distribue aucun contenu. Le développeur n'approuve ni ne promeut l'accès à des contenus protégés par des droits d'auteur. Les utilisateurs sont seuls responsables du respect de toutes les lois applicables.