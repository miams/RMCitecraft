# RMCitecraft Architecture Diagram

This diagram illustrates the high-level architecture of the RMCitecraft application, showing the relationships between the UI, controllers, services, data access layer, and external systems.

```mermaid
graph TD
    %% Styling
    classDef ui fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef logic fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef service fill:#fff3e0,stroke:#ef6c00,stroke-width:2px;
    classDef db fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px;
    classDef ext fill:#eeeeee,stroke:#616161,stroke-width:2px,stroke-dasharray: 5 5;

    subgraph "Frontend (NiceGUI)"
        A["Main Entry (main.py)"] --> B[Tab Manager]
        B --> C[Census Batch Tab]
        B --> D[Find a Grave Tab]
        B --> E[Citation Manager Tab]
    end
    class A,B,C,D,E ui;

    subgraph "Application Logic"
        C --> F[Census Batch Controller]
        D --> G[Find a Grave Controller]
        E --> H[Citation Manager Controller]
    end
    class F,G,H logic;

    subgraph "Core Services"
        F --> I[FamilySearch Automation]
        F --> J[LLM Extractor]
        G --> K[Find a Grave Automation]
        L[Image Processing Service]
        M[File Watcher]
    end
    class I,J,K,L,M service;

    subgraph "Data Access Layer"
        N[Census State Repository]
        O[Find a Grave State Repository]
        P[RootsMagic Repository]
        Q[Database Connection]
    end
    class N,O,P,Q db;

    subgraph "External Systems"
        R[FamilySearch.org]
        S[FindAGrave.com]
        T["LLM APIs (Claude/OpenAI)"]
        U[(Local State DB)]
        V[(RootsMagic DB + ICU)]
        W[File System]
    end
    class R,S,T,U,V,W ext;

    %% Relationships
    I -- Playwright --> R
    K -- Playwright --> S
    J -- LangChain --> T
    F -- Persist State --> N
    N -- SQLite --> U
    G -- Persist State --> O
    O -- SQLite --> U
    F -- Read/Write --> P
    P -- Uses --> Q
    Q -- SQL/ICU --> V
    M -- Notify --> L
    L -- Move/Rename --> W
```
