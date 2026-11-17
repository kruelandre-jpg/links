#!/usr/bin/env python3
"""Gera clinicas.html a partir de data/unidades.json e atualiza a contagem no index.html.

Uso (na raiz do repositório):
    python3 scripts/build_clinicas.py

A fonte canônica completa (com CPF, só no ambiente interno) fica em
/workspace/clinicas/. Este script lê apenas o JSON público, sem CPF.
"""
from __future__ import annotations

import json
import re
from collections import OrderedDict
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "unidades.json"
OUT = ROOT / "clinicas.html"
INDEX = ROOT / "index.html"

UF_NOMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo",
    "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina",
    "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins",
}


def load():
    if not DATA.exists():
        raise SystemExit(f"Não achei {DATA}. Copie unidades.publico.json da pasta canônica.")
    return json.loads(DATA.read_text(encoding="utf-8"))


def texto_contagem(meta: dict) -> str:
    if meta.get("texto_contagem"):
        # capitaliza só a primeira letra para uso em frase ou no botão
        t = meta["texto_contagem"].strip()
        return t[0].upper() + t[1:] if t else t
    n = meta.get("total_afiliadas", 0)
    e = meta.get("estados", 0)
    df = meta.get("inclui_df")
    if meta.get("total_matriz"):
        base = f"A matriz e {n} afiliadas em {e} estados"
    else:
        base = f"{n} clínicas em {e} estados"
    return base + " e o DF" if df else base


def tel_href(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("55"):
        return f"tel:+{digits}"
    if len(digits) >= 10:
        return f"tel:+55{digits}"
    return f"tel:{digits}"


def ig_href(handle: str) -> str:
    h = handle.strip()
    h = re.sub(r"\s*\(.*\)\s*$", "", h).strip()
    if h.startswith("@"):
        h = h[1:]
    return f"https://www.instagram.com/{h}/"


def is_url(s: str) -> bool:
    return bool(s) and s.lower().startswith(("http://", "https://"))


def endereco_bloco(u: dict) -> str:
    parts = [p for p in [u.get("endereco"), u.get("bairro")] if p]
    cidade = ", ".join([p for p in [u.get("cidade"), u.get("uf")] if p])
    if u.get("cep"):
        cidade = f"{cidade} · {u['cep']}" if cidade else u["cep"]
    lines = parts + ([cidade] if cidade else [])
    return "<br />".join(escape(x) for x in lines)


def meta_links(u: dict) -> str:
    bits = []
    for tel in u.get("telefones") or []:
        bits.append(
            f'<a href="{escape(tel_href(tel), quote=True)}">{escape(tel)}</a>'
        )
    for ig in u.get("instagram") or []:
        bits.append(
            f'<a href="{escape(ig_href(ig), quote=True)}" target="_blank" rel="noopener noreferrer">{escape(ig)}</a>'
        )
    for site in u.get("sites") or []:
        if is_url(site):
            label = re.sub(r"^https?://(www\.)?", "", site).rstrip("/")
            bits.append(
                f'<a href="{escape(site, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(label)}</a>'
            )
    return " · ".join(bits)


def card(u: dict, matriz: bool = False) -> str:
    classes = "clinic-card matriz-card" if matriz else "clinic-card"
    badge = '<span class="badge">Matriz</span>' if matriz else ""
    rotulo = u.get("numero_rotulo") or ""
    titulo = escape(u.get("nome") or "")
    local = ""
    if not matriz and u.get("local") and (u.get("nome") or "").lower().find("local ") >= 0:
        local = f'<p class="clinic-local">Local {u["local"]}</p>'
    obs = u.get("obs")
    obs_html = ""
    if obs and obs != "Matriz":
        obs_html = f'<p class="clinic-obs">{escape(obs)}</p>'
    num_html = "" if matriz else f'<span class="clinic-num">nº {escape(str(rotulo))}</span>'
    return f"""<article class="{classes}" data-numero="{escape(str(rotulo))}" data-uf="{escape(u.get('uf') or '')}">
  <header class="clinic-head">{badge}{num_html}<h3>{titulo}</h3></header>
  {local}
  <p class="clinic-addr">{endereco_bloco(u)}</p>
  <p class="clinic-links">{meta_links(u)}</p>
  {obs_html}
</article>"""


def agrupadas(unidades: list) -> OrderedDict:
    afil = [u for u in unidades if not u.get("e_matriz")]
    # RS first (home of the matriz), then other UFs alphabetically
    ufs = []
    seen = set()
    for u in afil:
        uf = u.get("uf")
        if uf and uf not in seen:
            ufs.append(uf)
            seen.add(uf)
    ufs.sort(key=lambda x: (0 if x == "RS" else 1, x))
    groups = OrderedDict()
    for uf in ufs:
        groups[uf] = [u for u in afil if u.get("uf") == uf]
    return groups


def map_points(unidades: list) -> list:
    pts = []
    for u in unidades:
        if u.get("lat") is None or u.get("lon") is None:
            continue
        pts.append({
            "nome": u.get("nome"),
            "cidade": u.get("cidade"),
            "uf": u.get("uf"),
            "lat": u["lat"],
            "lon": u["lon"],
            "matriz": bool(u.get("e_matriz")),
            "rotulo": u.get("numero_rotulo"),
        })
    return pts


def render(data: dict) -> str:
    meta = data.get("meta") or {}
    unidades = data.get("unidades") or []
    matriz = next((u for u in unidades if u.get("e_matriz")), None)
    groups = agrupadas(unidades)
    contagem = texto_contagem(meta)
    atualizado = meta.get("atualizado_em") or ""
    if atualizado:
        # 2026-11-17 -> 17/11/2026
        parts = atualizado.split("-")
        if len(parts) == 3:
            atualizado_br = f"{parts[2]}/{parts[1]}/{parts[0]}"
        else:
            atualizado_br = atualizado
    else:
        atualizado_br = ""
    pts = map_points(unidades)
    map_json = json.dumps(pts, ensure_ascii=False)
    map_block = ""
    if pts:
        map_block = f"""
<section class="mapa-wrap" aria-label="Mapa das clínicas">
  <div id="mapa" role="application" aria-label="Mapa com a matriz e as clínicas afiliadas"></div>
  <p class="mapa-nota">Os pinos usam o OpenStreetMap. Alguns caem na rua ou na cidade, não na porta exata.</p>
</section>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
(function () {{
  var pontos = {map_json};
  var mapa = document.getElementById("mapa");
  if (!mapa || !window.L || !pontos.length) return;
  var map = L.map("mapa", {{ scrollWheelZoom: false }});
  L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
    attribution: "&copy; OpenStreetMap",
    maxZoom: 18
  }}).addTo(map);
  var bounds = [];
  pontos.forEach(function (p) {{
    var cor = p.matriz ? "#3a3c38" : "#66b2e0";
    var icon = L.divIcon({{
      className: p.matriz ? "pin pin-matriz" : "pin",
      html: '<span style="background:' + cor + '"></span>',
      iconSize: [22, 22],
      iconAnchor: [11, 11]
    }});
    var titulo = p.matriz ? "Matriz · " + p.nome : p.nome;
    var m = L.marker([p.lat, p.lon], {{ icon: icon }}).addTo(map);
    m.bindPopup("<strong>" + titulo + "</strong><br>" + (p.cidade || "") + " · " + (p.uf || ""));
    bounds.push([p.lat, p.lon]);
  }});
  map.fitBounds(bounds, {{ padding: [28, 28], maxZoom: 6 }});
}})();
</script>
"""
    secoes = []
    if matriz:
        secoes.append('<section class="bloco-matriz" aria-labelledby="titulo-matriz">')
        secoes.append('<h2 id="titulo-matriz">Matriz</h2>')
        secoes.append(card(matriz, matriz=True))
        secoes.append("</section>")
    for uf, lista in groups.items():
        nome = UF_NOMES.get(uf, uf)
        hid = f"uf-{uf.lower()}"
        secoes.append(f'<section class="bloco-uf" aria-labelledby="{hid}" id="{hid}">')
        secoes.append(f"<h2 id=\"{hid}-titulo\">{escape(nome)} <span>({escape(uf)})</span></h2>")
        for u in lista:
            secoes.append(card(u))
        secoes.append("</section>")
    lista_html = "\n".join(secoes)
    data_nota = f"Lista oficial atualizada em {escape(atualizado_br)}." if atualizado_br else ""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Clínicas Proregen · Dr. André Kruel</title>
    <meta
      name="description"
      content="Matriz da Proregen em Bento Gonçalves e clínicas afiliadas no Brasil. {escape(contagem)}."
    />
    <meta name="theme-color" content="#F4F9FC" />
    <meta property="og:title" content="Clínicas Proregen · Dr. André Kruel" />
    <meta
      property="og:description"
      content="{escape(contagem)}."
    />
    <meta property="og:type" content="website" />
    <meta property="og:locale" content="pt_BR" />
    <link rel="icon" href="assets/symbol.svg" type="image/svg+xml" />
    <link rel="stylesheet" href="css/styles.css" />
  </head>
  <body class="page-clinicas">
    <main>
      <header class="intro">
        <a href="index.html" class="logo-link">
          <img
            class="logo"
            src="assets/logo-horizontal.svg"
            width="220"
            height="77"
            alt="Proregen"
          />
        </a>
        <h1>Clínicas Proregen</h1>
        <p class="role">Rede</p>
        <p class="registry">{escape(contagem)}</p>
        <p class="lede">
          A matriz fica em Bento Gonçalves (RS), com o Dr. André Kruel.
          As afiliadas têm equipe local. Tubarão (SC) aparece com dois endereços
          e conta como uma afiliada.
        </p>
        <p class="lede lede-data">{data_nota}</p>
      </header>

      {map_block}

      <div class="lista-clinicas">
        {lista_html}
      </div>

      <p class="back">
        <a href="index.html">Voltar aos links</a>
      </p>

      <footer class="footer">
        <nav class="social" aria-label="Redes">
          <a
            href="https://www.instagram.com/dr.andrekruel/"
            target="_blank"
            rel="noopener noreferrer"
          >
            Instagram
            <span class="sr-only">Abre em uma nova aba.</span>
          </a>
          <a
            href="https://www.youtube.com/channel/UC19XxhiJrYcz3rzI4o6zwag"
            target="_blank"
            rel="noopener noreferrer"
          >
            YouTube
            <span class="sr-only">Abre em uma nova aba.</span>
          </a>
        </nav>
      </footer>
    </main>
  </body>
</html>
"""


INDEX_START = "<!-- CONTAGEM-CLINICAS:inicio -->"
INDEX_END = "<!-- CONTAGEM-CLINICAS:fim -->"


def patch_index(contagem: str) -> None:
    if not INDEX.exists():
        return
    text = INDEX.read_text(encoding="utf-8")
    inner = (
        f"{INDEX_START}\n"
        f'          <span>Encontre uma clínica Proregen'
        f'<small class="cta-count">{escape(contagem)}</small></span>\n'
        f"          {INDEX_END}"
    )
    if INDEX_START in text and INDEX_END in text:
        text = re.sub(
            re.escape(INDEX_START) + r".*?" + re.escape(INDEX_END),
            inner,
            text,
            count=1,
            flags=re.S,
        )
    else:
        # first run: wrap the existing button label
        old = "<span>Encontre uma clínica Proregen</span>"
        if old not in text:
            print("Aviso: não achei o rótulo do botão de clínicas no index.html")
            return
        text = text.replace(old, inner, 1)
    INDEX.write_text(text, encoding="utf-8")
    print(f"Atualizei a contagem no index.html: {contagem}")


def main() -> None:
    data = load()
    html = render(data)
    OUT.write_text(html, encoding="utf-8")
    print(f"Gerei {OUT}")
    patch_index(texto_contagem(data.get("meta") or {}))


if __name__ == "__main__":
    main()
