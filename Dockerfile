FROM python:3.12-slim

LABEL name="Wawacity-Stremio-Addon-v2" \
      description="Accès au contenu de Wawacity via Stremio & AllDebrid (non officiel)" \
      url="https://github.com/spel987/Wawacity-Stremio-Addon"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7000

CMD ["python", "-m", "wawacity.main"]
