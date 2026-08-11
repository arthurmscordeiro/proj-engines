# Radar IA

O Radar IA coleta a API gratuita da Artificial Analysis e os datasets públicos
prioritários da Epoch AI na mesma execução. Ele preserva histórico local,
arquiva as fontes brutas e cria novos Excels a cada rodada.

## Primeira instalação no VS Code

1. Instale Python 3.9 ou superior.
2. Abra esta pasta no VS Code e abra o terminal integrado (`Terminal` → `New Terminal`).
3. Configure a chave:

```bash
cp .env.example .env
```

Abra `.env` no VS Code, cole a chave após `AA_API_KEY=` e salve. Esse arquivo
fica somente no seu computador e não é enviado ao GitHub.

## Coleta mensal

Rode:

```bash
python radar_ia.py
```

No VS Code, também é possível usar `Terminal` → `Run Task...` → `Rodar Radar IA`.

O resultado da Artificial Analysis fica em `outputs AA/` e o da Epoch AI em
`outputs Epoch AI/`. Cada execução cria um novo Excel com data e hora no nome;
nenhuma versão anterior é sobrescrita.

O histórico normalizado da Artificial Analysis fica em `data/model_history.csv`
e a resposta bruta em `data/raw/`. Para a Epoch, `data/epoch/source_history.csv`
registra data, URL e hash SHA-256 de cada fonte; os ZIPs originais são guardados
em `data/epoch/raw/` somente quando o conteúdo mudou. Isso evita duplicatas e
permite auditoria das revisões da fonte.

O histórico é orientado a mudanças: a primeira execução registra todos os
modelos e as execuções seguintes acrescentam uma nova linha somente quando um
campo monitorado mudou. A aba `Execuções` de cada Excel mostra quantos modelos
foram novos, alterados ou permaneceram iguais naquela rodada.

As pastas `data/`, `outputs AA/` e `outputs Epoch AI/` ficam somente no
computador em que a coleta ocorre. Faça backup delas regularmente: é ali que
está o seu histórico.

O arquivo preserva a versão do Intelligence Index retornada pela API, porque
comparações entre versões metodológicas diferentes requerem cautela.

## Abas para gráficos da Artificial Analysis

Cada Excel da Artificial Analysis inclui também:

- `Highlights Intelligence`, `Highlights Speed` e `Highlights Cost`: seleção
  editorial de modelos exibida na homepage da Artificial Analysis, ordenada
  pela métrica da aba. Variações low/medium/high/xhigh/max de uma mesma família
  são reduzidas à maior configuração de effort.
- `Intelligence x Cost`: dados da seleção-padrão da Artificial Analysis para o
  gráfico de dispersão entre Intelligence Index e custo por tarefa.
- `Intelligence x Abertura`: os 25 modelos com maior Intelligence Index cuja
  classificação entre proprietary/open weights foi confirmada via Epoch AI.
- `Top 25 Agentic`: ranking dos 25 modelos com maior Agentic Index, também sem
  duplicar variantes de effort.

A API gratuita não disponibiliza os flags editoriais de destaque. Por isso as
seleções públicas da homepage são registradas explicitamente no código, com a
data de referência, em vez de serem substituídas por um top-N arbitrário.

## O que vem no Excel da Epoch AI

- `ECI`: score, lançamento, organização, país e acessibilidade.
- Capacidade acumulada de compute: por organização, por chip e trimestral.
- `Power - total`: série trimestral consolidada dos data centers cobertos pela
  Epoch, com compute (H100-equivalents), potência de TI e potência total da
  instalação. Os períodos futuros são identificados como projeções da Epoch.
- `Power - owner` e `Power - país`: a mesma série, segmentada por proprietário
  e país. Cada trimestre usa a última observação disponível de cada data center
  até o fim daquele trimestre.
- Data centers: snapshot, timeline (inclusive estimativas futuras da Epoch) e
  quantidades de chips; incluem owner, primary user e country quando informados.
- Empresas: cadastro, funding rounds, receita, equipe, uso e gasto de compute.
- `Fontes`: URL, horário, hash e status de cada download.

Dados: [Artificial Analysis](https://artificialanalysis.ai/) e
[Epoch AI](https://epoch.ai/data). A atribuição é obrigatória conforme as
licenças das fontes.
