# Yearn News

## Get Pilled

[**The Blue Pill**](https://news.yearn.fi/)

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/johnnyonline/yearn-news.git
   cd yearn-news
   ```

2. **Set up virtual environment**
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   # Install all dependencies
   uv sync
   ```

   > Note: This project uses [uv](https://github.com/astral-sh/uv) for faster dependency installation. If you don't have uv installed, you can install it with `pip install uv` or follow the [installation instructions](https://github.com/astral-sh/uv#installation).

4. **Environment setup**
   ```bash
   cp .env.example .env
   # Edit .env with your RPC URLs and GraphQL endpoints

   # Load environment variables into your shell session
   export $(grep -v '^#' .env | xargs)
   ```

   `ENVIO_GRAPHQL_URL` is used to query recent `StrategyChanged` events for the weekly update.
   `KONG_GRAPHQL_URL` is used to fetch vault metadata/APR/TVL (defaults to `https://kong.yearn.fi/api/gql`).

## Usage

Run:
```shell
python src/generate.py
```

Output is written to `output.md` in Markdown format.

## Code Style

Format and lint code with ruff:
```bash
# Format code
ruff format .

# Lint code
ruff check .

# Fix fixable lint issues
ruff check --fix .
```

Type checking with mypy:
```bash
mypy .
```
