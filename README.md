# SysAVA

Plataforma educacional web construída com NiceGUI e SQLite.

## Funcionalidades

- **Aulas**: Conteúdo por turma e disciplina com suporte a vídeo
- **Quizzes**: Questionários interativos por aula
- **Fórum**: Discussões por aula
- **Pontos**: Sistema de pontos com participação (NM1/NM2)
- **Notas**: Cálculo automático de notas (NM1, NM2, NM3)
- **Frequência**: Controle de presença
- **Gerenciamento**: CRUD de turmas, disciplinas e alunos

## Pré-requisitos

- Python 3.11+
- Supabase (para sync de dados)

## Instalação

```bash
# Clonar o repositório
git clone https://github.com/hiseg10/sysava-nicegui.git
cd sysava-nicegui

# Criar ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas credenciais do Supabase

# Executar
python main.py
```

## Variáveis de Ambiente

| Variável | Descrição |
|----------|-----------|
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_KEY` | Chave de serviço do Supabase |
| `STORAGE_SECRET` | Segredo para sessões (gerado automaticamente no Render) |
| `PORT` | Porta do servidor (padrão: 8080) |
| `SYSAVA_DB_PATH` | Caminho do banco SQLite (opcional, padrão: `data/escola_ativa.db`) |

## Deploy no Render

1. Criar conta no [Render](https://render.com)
2. Criar novo Web Service
3. Conectar repositório GitHub
4. Configurar:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python main.py`
5. Adicionar variáveis de ambiente no painel do Render

**Importante**: O Render usa disco persistente. Configure o `SYSAVA_DB_PATH` para um diretório persistente como `/data/escola_ativa.db` e crie um Volume no Render apontando para `/data`.

## Estrutura

```
sysava-nicegui/
├── core/           # Lógica de negócio
│   ├── auth.py     # Autenticação
│   ├── db.py       # Conexão SQLite
│   ├── scores.py   # Sistema de notas
│   └── ...
├── ui/             # Interface (NiceGUI)
│   ├── aulas.py    # Página de aulas
│   ├── perfil.py   # Perfil do usuário
│   └── ...
├── data/           # Dados locais
├── main.py         # Ponto de entrada
└── requirements.txt
```

## Licença

MIT
