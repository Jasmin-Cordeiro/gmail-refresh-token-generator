#!/usr/bin/env python3
"""Gera o refresh_token OAuth2 do Gmail (fluxo Authorization Code + PKCE).

Uso:
    python gerar_token.py                      # abre o browser padrão
    python gerar_token.py --no-browser         # só imprime a URL (cole numa janela anônima)
    python gerar_token.py --config config.prod.json
"""
import argparse
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import webbrowser

from google_auth_oauthlib.flow import Flow

TIMEOUT_SEGUNDOS = 180


def carregar_config(caminho: Path) -> dict:
    if not caminho.exists():
        sys.exit(f"'{caminho}' não encontrado. Copie config.example.json e preencha.")
    config = json.loads(caminho.read_text(encoding="utf-8"))
    faltando = [k for k in ("client_id", "client_secret", "redirect_uri", "scopes") if not config.get(k)]
    if faltando or "SEU_CLIENT" in config["client_id"] + config["client_secret"]:
        sys.exit(f"Config incompleta em '{caminho}': {faltando or 'client_id/client_secret ainda são placeholders'}")
    return config


def aguardar_callback(redirect_uri: str, state_esperado: str) -> str:
    """Sobe um servidor local e devolve a URL completa do callback."""
    uri = urlparse(redirect_uri)
    resultado: dict = {}
    recebido = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlparse(self.path).path != uri.path:
                self.send_error(404)
                return
            params = parse_qs(urlparse(self.path).query)
            if params.get("state", [None])[0] != state_esperado:
                resultado["erro"] = "state inválido (possível callback forjado)"
            elif "error" in params:
                resultado["erro"] = params["error"][0]
            else:
                resultado["url"] = f"{uri.scheme}://{uri.netloc}{self.path}"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>Autenticado! Pode fechar esta janela.</h2>".encode())
            recebido.set()

        def log_message(self, *_):
            pass

    try:
        servidor = HTTPServer((uri.hostname, uri.port or 80), Handler)
    except OSError as e:
        sys.exit(f"Não foi possível abrir a porta {uri.port} ({e}). Feche o processo que a usa e tente de novo.")

    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        if not recebido.wait(TIMEOUT_SEGUNDOS):
            sys.exit(f"Timeout de {TIMEOUT_SEGUNDOS}s aguardando o login.")
    finally:
        servidor.shutdown()
    if "erro" in resultado:
        sys.exit(f"Autorização falhou: {resultado['erro']}")
    return resultado["url"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--no-browser", action="store_true", help="não abre o browser; imprime a URL")
    args = parser.parse_args()

    config = carregar_config(args.config)
    flow = Flow.from_client_config(
        {"web": {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "auth_uri": config.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
            "token_uri": config.get("token_uri", "https://oauth2.googleapis.com/token"),
            "redirect_uris": [config["redirect_uri"]],
        }},
        scopes=config["scopes"].split(),
        redirect_uri=config["redirect_uri"],
        autogenerate_code_verifier=True,  # PKCE
    )
    auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")

    print("Faça login com a conta desejada.")
    if args.no_browser or not webbrowser.open(auth_url):
        print(f"\nAbra esta URL (de preferência em janela anônima):\n\n{auth_url}\n")

    # oauthlib exige https; o callback em localhost é http por definição (tráfego não sai da máquina).
    if urlparse(config["redirect_uri"]).hostname in ("localhost", "127.0.0.1"):
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    flow.fetch_token(authorization_response=aguardar_callback(config["redirect_uri"], state))

    refresh_token = flow.credentials.refresh_token
    if not refresh_token:
        sys.exit("O Google não retornou refresh_token. Revogue o acesso do app na conta e tente de novo.")
    print(f"\nrefresh_token:\n{refresh_token}")


if __name__ == "__main__":
    main()
