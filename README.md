# Quantum Random AMA Questions

Fetches Mindscape AMA questions from Patreon and sorts them using quantum random numbers from the [ANU QRNG service](https://qrng.anu.edu.au).

Inspired by Trevor Morrissey's suggestion in the [May 2023 AMA](https://www.preposterousuniverse.com/podcast/2023/05/08/ama-may-2023/) to use quantum randomness to ensure every question gets answered in at least one branch of the Everettian multiverse.

## Usage

```bash
python quantum-random-ama-questions.py [--quantum] [--gist] [--cache]
```

- `--quantum`: Use ANU Quantum RNG (requires `ANU_QUANTUM_API_KEY`)
- `--gist`: Upload results to GitHub Gist (requires `GITHUB_TOKEN`)
- `--cache`: Fetch Patreon comment URLs from cache when available (always writes to cache)

## Environment Variables

Create a `.env` file with:
```
ANU_QUANTUM_API_KEY=your_anu_api_key
GITHUB_TOKEN=your_github_token
PATREON_COOKIE=your_patreon_session_cookie
```

## Dependencies

```bash
pip install requests python-dotenv
```
