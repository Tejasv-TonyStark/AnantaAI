# AnantaAI

**AnantaAI** is a 5-day AI-assisted engineering project focused on building five small, working, industry-style systems and integrating them into one secure multi-agent AI platform.

The name **Ananta** represents limitless scale and is inspired by **Ananta Shesha**, associated with Lord Vishnu.

The platform is divided into five core modules.

## 1. Sudarshan — Secure AI Gateway

Sudarshan acts as the security layer of AnantaAI. It handles user authentication, password hashing, JWT-based login, Role-Based Access Control, permissions, protected APIs, rate limiting, and audit logging. It decides who can access each AI service.

**Tech:** Python, FastAPI, PostgreSQL, Redis, SQLAlchemy, JWT, Docker.

## 2. Smriti — Enterprise RAG Agent

Smriti acts as the knowledge system of AnantaAI. It allows users to ask questions from internal documents such as company policies, SOPs, guidelines, and technical documentation.

The system retrieves relevant information and uses an LLM to generate a grounded response with supporting sources.

**Tech:** Python, FastAPI, RAG, embeddings, vector database, LLM.

## 3. Manthan — Text-to-SQL Agent

Manthan converts natural-language questions into SQL queries.

For example:

`Show the top 5 products by revenue.`

The agent understands the database schema, generates SQL, validates the query, executes it safely, and returns the result.

**Tech:** Python, FastAPI, PostgreSQL, SQLAlchemy, SQL, LLM.

## 4. Garuda — AI Cloud Security Agent

Garuda analyzes cloud infrastructure and security information. It can inspect logs, audit events, cloud configurations, and suspicious activity to produce security findings and recommendations.

**Tech:** Python, FastAPI, AWS, cloud APIs, LLM.

## 5. Vishvaksena — Multi-Agent Incident Commander

Vishvaksena coordinates the other agents during complex tasks or security incidents.

For example, Garuda can investigate an incident, Manthan can query related data, Smriti can retrieve response procedures, and Vishvaksena can combine their results into one final incident report.

## Development Goal

Each module is built as a small, independently testable prototype before integration.

The final AnantaAI platform demonstrates:

**Backend Engineering + AI Agents + Security + Databases + Cloud + RAG + Data Engineering + Multi-Agent Orchestration.**
