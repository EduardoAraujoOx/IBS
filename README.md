# Estimativa CPT/CPA do IBS para o Espírito Santo

Este repositório organiza uma rotina reprodutível para levantar dados do Siconfi/FINBRA e estimar, para o Espírito Santo, o coeficiente de participação histórica no IBS de transição.

O objetivo inicial é montar a tabela de apoio ao cálculo de:

- ICMS do Espírito Santo por ano;
- RBR nacional, definida como ICMS estadual + ISS municipal;
- deflator `RBR_2025 / RBR_a`;
- receita corrigida `RPC_a`;
- receita média do ES `RME_ES`;
- coeficiente de participação histórica `CPT_ES`;
- coeficiente de participação atual `CPA_ES`;
- diferença `CPT_ES - CPA_ES`.

A rotina foi desenhada para manter a etapa metodológica auditável. Antes de fechar o número final, ela gera uma tabela de diagnóstico com as linhas candidatas de ICMS, ISS, Fundeb, cota-parte e transferências existentes nos arquivos do Siconfi.

## Estrutura

```text
.
├── config/
│   └── parametros.yml
├── data/
│   ├── raw/          # arquivos brutos baixados do Siconfi
│   ├── interim/      # tabelas intermediárias e diagnósticos
│   └── processed/    # bases tratadas
├── docs/
│   └── index.html    # página HTML com o resumo do cálculo
├── outputs/          # tabela final em CSV e XLSX
├── scripts/
│   ├── 01_baixar_rreo.py
│   ├── 02_diagnosticar_linhas.py
│   ├── 03_calcular_cpt_es.py
│   └── 04_gerar_html.py
└── src/
    └── siconfi_ibs/
```

## Como rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

pip install -r requirements.txt

python scripts/01_baixar_rreo.py
python scripts/02_diagnosticar_linhas.py
python scripts/03_calcular_cpt_es.py
python scripts/04_gerar_html.py
```

Os principais resultados ficam em:

```text
outputs/tabela_cpt_es.csv
outputs/tabela_cpt_es.xlsx
outputs/resumo_cpt_es.txt
docs/index.html
```

## Página HTML

O arquivo `docs/index.html` apresenta um resumo visual com CPT, CPA, diferença em pontos percentuais, ano-base e tabela anual de cálculo.

Para publicar no GitHub Pages, use a configuração do repositório: **Settings > Pages > Build and deployment > Deploy from a branch**, selecionando a branch `main` e a pasta `/docs`.

Depois disso, a página deve ficar disponível em:

```text
https://eduardoaraujoox.github.io/IBS/
```

## Observação metodológica importante

A versão inicial calcula uma base automática usando as linhas de ICMS e ISS identificadas no RREO. Como o ponto sensível da metodologia é a definição de “ICMS líquido do ES”, a rotina também gera:

```text
data/interim/linhas_candidatas_icms_iss_fundeb.csv
```

Essa tabela deve ser conferida antes de usar o número final em documento institucional. A partir dela, é possível ajustar os padrões no arquivo `config/parametros.yml`, especialmente para tratar cota-parte municipal e Fundeb.

## Execução pelo GitHub Actions

O workflow `Atualizar tabela CPT ES` pode ser disparado manualmente na aba **Actions** do GitHub. Ele baixa os dados, calcula a tabela, gera `docs/index.html`, atualiza a página no repositório e disponibiliza os arquivos finais como artefatos da execução.
