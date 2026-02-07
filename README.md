# AI-Assisted Configuration Management System

A microservices system that modifies Kubernetes-style application configurations using natural language. Powered by a local LLM (Mistral 7B via Ollama) -- no cloud APIs, everything runs on your machine.

```bash
curl -X POST http://localhost:5003/message \
  -H "Content-Type: application/json" \
  -d '{"input": "set tournament service memory to 1024mb"}'
```

---

## Architecture

Four containerized services orchestrated with Docker Compose:

```
          User Request
               |
               v
        +--------------+
        |  Bot Server   |  :5003  (orchestrator)
        +------+-------+
               |
       +-------+-------+--------+
       |               |        |
       v               v        v
  +---------+   +---------+  +--------+
  | Schema  |   | Values  |  | Ollama |
  | Server  |   | Server  |  | (LLM)  |
  | :5001   |   | :5002   |  | :11434 |
  +---------+   +---------+  +--------+
```

| Service | Port | Role |
|---------|------|------|
| **bot-server** | 5003 | Orchestrates the flow -- receives user input, calls LLM, applies changes, validates |
| **schema-server** | 5001 | Serves JSON Schema files for validation |
| **values-server** | 5002 | Serves current configuration values |
| **ollama** | 11434 | Runs Mistral 7B locally |

Services discover each other via Docker DNS. Only the bot-server is exposed externally.

---

## How It Works

1. User sends a natural language request to the bot server
2. **LLM call #1**: Identifies which app the user is referring to (chat / matchmaking / tournament)
3. Bot fetches the app's schema and current values from the other services
4. **LLM call #2**: Determines what field to change and to what value, returns `{"path": "some.nested.path", "value": 1024}`
5. Bot applies the change in Python, validates against the JSON Schema
6. Returns the modified configuration

---

## Getting Started

### Prerequisites

- Docker with at least **10GB RAM** allocated (Mistral 7B needs ~6GB)
- Docker Compose

### Run

```bash
docker compose up --build
```

First run takes a few minutes -- it pulls and loads the Mistral model. Once all services are up:

```bash
# Set memory limit
curl -X POST http://localhost:5003/message \
  -H "Content-Type: application/json" \
  -d '{"input": "set tournament service memory to 1024mb"}'

# Change environment variable
curl -X POST http://localhost:5003/message \
  -H "Content-Type: application/json" \
  -d '{"input": "set GAME_NAME env to toyblast for matchmaking service"}'

# Adjust CPU limit
curl -X POST http://localhost:5003/message \
  -H "Content-Type: application/json" \
  -d '{"input": "lower cpu limit of chat service to %80"}'
```

---

## Design Decisions

### Why Mistral 7B?

Tested multiple models before settling:

- **llama3.2 (3B)** -- returned empty responses
- **phi3:mini (3.8B)** -- couldn't follow simple instructions like "reply with one word"
- **Mistral (7B)** -- the minimum that reliably followed structured prompts

Uses more RAM, but smaller models simply couldn't handle "return ONLY valid JSON" type instructions.

### Why Two LLM Calls Instead of One?

Splitting app identification and config modification into separate calls made debugging much easier. When something broke, I could immediately tell if it was the app detection or the modification logic.

### Why Path-Based Output Instead of Full JSON?

Originally tried asking the LLM to return the entire modified config. The configs are 150-200 lines and the output kept getting truncated mid-JSON. Switched to having the LLM return just a path and value -- much more reliable since it's always a tiny JSON response.

### Why Schema Isn't Sent to the LLM

The assignment called for sending both schema and values to the LLM. I tried this and it was a disaster -- response times went from ~10 seconds to **over 10 minutes**, and accuracy dropped. The combined schema + values is ~1700 lines, way too much context.

Now I only send the values (which already contain the structure the LLM needs to find valid paths) and use the schema strictly for post-generation validation. 10x faster, still validates.

---

## Tradeoffs

| Decision | Downside | Why |
|----------|----------|-----|
| Mistral 7B | Higher RAM usage | Only model that worked reliably |
| Two LLM calls per request | Slower (~20s total) | Much easier to debug |
| Path-based modification | More application code | Avoids output truncation |
| Schema for validation only | Less context for LLM | 10x faster response time |

---

## Limitations

- One configuration change per request
- Changes are validated but not persisted back to files
- No authentication or rate limiting
- No retry logic for LLM timeouts

---

## Tech Stack

- **Python 3.11** / Flask for all services
- **Ollama** running Mistral 7B
- **Docker Compose** for orchestration
- **jsonschema** for validation
