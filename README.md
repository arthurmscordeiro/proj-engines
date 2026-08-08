# Radar IA

O Radar IA coleta mensalmente a API gratuita da Artificial Analysis, acrescenta
os dados a uma base histórica local e cria um novo Excel a cada execução.

## Primeira instalação no VS Code

1. Instale Python 3.9 ou superior.
2. Abra esta pasta no VS Code e abra o terminal integrado (`Terminal` → `New Terminal`).
3. Crie e ative um ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

No Windows, a ativação é:

```powershell
.venv\Scripts\Activate.ps1
```

4. Instale a dependência e configure a chave:

```bash
pip install -r requirements.txt
cp .env.example .env
```

Abra `.env` no VS Code, cole a chave após `AA_API_KEY=` e salve. Esse arquivo
fica somente no seu computador e não é enviado ao GitHub.

## Coleta mensal

Com o ambiente virtual ativado, rode:

```bash
python radar_ia.py
```

O histórico normalizado fica em `data/model_history.csv`; a resposta bruta de
cada coleta é arquivada em `data/raw/` para auditoria. Cada execução cria um
novo Excel com data e hora no nome, em `outputs/`; nenhuma versão anterior é
sobrescrita.

As pastas `data/` e `outputs/` ficam somente no computador em que a coleta
ocorre. Faça backup delas regularmente: é ali que está o seu histórico.

O arquivo preserva a versão do Intelligence Index retornada pela API, porque
comparações entre versões metodológicas diferentes requerem cautela.

Dados: Artificial Analysis (https://artificialanalysis.ai/). A atribuição é
obrigatória pela licença da API gratuita.
