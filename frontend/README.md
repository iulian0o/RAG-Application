# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])

```

You can also install [eslint-plugin-react-x](https://npmx.dev/package/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://npmx.dev/package/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])

```
## Using Ask with retrievers (V3)

Open the Ask view, select at least one indexed document, then choose the
retrievers: **Dense**, **BM25** and **Concept Graph**. They can be combined.
With several retrievers, the backend fuses their rankings with reciprocal
rank fusion (RRF) and only the fused top-k passages reach the model.
An empty retriever selection is rejected.

Each supporting passage shows:

- its fused rank (`#1`) and the rank each retriever gave it
  (for example `dense: 2 · bm25: 1`);
- the cosine distance, only when Dense found the passage;
- for Concept Graph results, the entity matched in the question, each edge
  traversed (subject, relation, object) and the source quote of each edge.

The line under the answer lists the retrievers, candidate depth and RRF k used.
If nothing relevant is retrieved, the answer is "Insufficient evidence".

### Concept Graph

The graph exists only for the indexed Kestrel documents. Upload the five files
of `docs/kestrel`, build their indexes with the same settings (800 / 80), then
build the graph from the `backend` directory with the backend environment
active. This calls the LLM provider and consumes tokens:

```powershell
python -m app.build_concept_graph kestrel
```

Inspect ranked paths in the existing graph:

```powershell
python -m app.build_concept_graph kestrel --question "Aurora Reports"
```

The graph is tied to the active indexes. After re-indexing, the Ask view
reports that the graph is stale: rebuild it, or uncheck Concept Graph.

### Benchmark and Evaluation view

Compare retrieval configurations from the `backend` directory:

```powershell
python -m app.benchmark_v3 kestrel --config dense --config dense+bm25
python -m app.benchmark_v3 kestrel --config dense+bm25@bm25=0.5
```

Each configuration is saved under `evaluation/results/` as `v3-<run_id>.json`,
with a comparison CSV. In the Evaluation view, open a run by its ID: the
**Retrieval configuration** section shows the retrievers, fusion mode, weights,
RRF k, candidate depth, Git commit and mean latency; each question shows its
retrieval latency and model usage when they were recorded. The Run evaluation
button runs the dense-only V2 evaluation.

### Tests

```powershell
cd backend
python -m pytest -q
cd ../frontend
npm run build
```