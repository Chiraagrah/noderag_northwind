# Frontend Architecture

## Component Tree

```
App
├── KeyboardShortcuts          (render-null, attaches window keydown)
├── Topbar                     (fixed 40px bar)
│   ├── wordmark
│   ├── StatPill × 3           (nodes / edges / types from /api/graph/stats)
│   └── reload button + api status
└── AppShell                   (flex row, calc(100vh - 40px))
    ├── ErrorBoundary
    │   ├── GraphCanvas        (D3 host — owns the SVG)
    │   │   ├── LoadingState   (static SVG skeleton)
    │   │   ├── ErrorState     (retry button)
    │   │   ├── <svg>          (D3 renders inside <g ref={containerRef}>)
    │   │   ├── FilterBar      (absolute top-left, N1-N7 toggle buttons)
    │   │   ├── TypeLegend     (absolute bottom-left, <table>)
    │   │   └── ZoomControls   (absolute bottom-right, +/−/1:1)
    │   └── AnimatePresence
    │       └── NodeInspector  (absolute right-0, slide-in panel)
    └── ErrorBoundary
        └── QueryConsole       (flex column, full height)
            ├── header bar     (QUERY CONSOLE label + clear button)
            ├── scroll area
            │   ├── RetrievalLog   (AnimatePresence rows, one per SSE event)
            │   ├── AnswerPane     (word-by-word reveal, collapsible reasoning)
            │   └── FollowUpList   (text-link buttons)
            └── QueryInput     (textarea + example queries)
```

---

## Data Flow: Query → Store → D3 Update

```
User types question
        │
        ▼
QueryInput.onKeyDown(Enter)
        │
        ▼
useQueryStream.submitQuery(question)
        │
        ├─► queryStore.startQuery()        clears steps, answer, error
        │
        ├─► fetch POST /api/query/         SSE stream begins
        │       │
        │       ├─► event "seed"   ──► queryStore.addStep(stamped)
        │       ├─► event "seed"   ──► queryStore.addStep(stamped)
        │       ├─► event "ppr"    ──► queryStore.addStep(stamped)
        │       │                  ──► graphStore.setHighlights(pprNodeIds)
        │       │                           │
        │       │                           ▼
        │       │                   useD3Graph effect fires
        │       │                   renderer.update(highlightedIds, dimmedIds)
        │       │                   D3 transitions node opacity (200ms)
        │       │
        │       ├─► event "kcore"  ──► queryStore.addStep(stamped)
        │       ├─► event "context"──► queryStore.addStep(stamped)
        │       └─► event "answer" ──► queryStore.setAnswer(data)
        │                          ──► queryStore.addStep(stamped)
        │
        ▼
RetrievalLog re-renders          (reads queryStore.steps)
AnswerPane re-renders            (reads queryStore.answer)
FollowUpList re-renders          (reads queryStore.answer.suggested_follow_ups)
GraphCanvas does NOT re-render   (reads only graphStore — different store)
```

---

## D3 Lifecycle: init / update / destroy

```
GraphCanvas mounts
        │
        ▼
useEffect([d3Data]) fires
        │
        ├─► old renderer?.destroy()    stops sim, removes all DOM nodes, unbinds zoom
        │
        └─► new GraphRenderer(svgEl, containerEl)
                │
                ▼
            renderer.init(d3Data, callbacks)
                │
                ├─► deep-copy nodes and links   (D3 mutates positions; store stays clean)
                ├─► d3.zoom attached to <svg>
                ├─► <g class="edges"> + <line> elements
                ├─► <g class="nodes"> + <g.node> groups (circle + text per node)
                ├─► d3.drag attached to node groups
                ├─► d3.forceSimulation starts
                │       alphaDecay=0.028, velocityDecay=0.45
                │       forceLink / forceManyBody / forceCenter / forceCollide
                │       tick: updates line x1/y1/x2/y2 and node transforms
                │
                └─► sim.on("end") → _startDrift(nodes)
                        d3.timer: sinusoidal ±2.5px offset per node at ~8-9s period

Highlights change (PPR event)
        │
        ▼
useEffect([highlightedIds, dimmedIds]) fires
        │
        └─► renderer.update(highlightedIds, dimmedIds)
                d3 transitions (200ms):
                  highlighted: fill-opacity 0.25, stroke-width 2.5
                  dimmed:      fill-opacity 0.06, text opacity 0.15
                  edges:       highlighted connections 0.8, others 0.1
                drift timers stopped while highlights are active

visibleTypes changes (FilterBar toggle)
        │
        ▼
useEffect([visibleTypesKey]) fires          (string key avoids Set identity issues)
        │
        └─► renderer.filter(visibleTypes)
                node opacity 0/1, pointer-events auto/none (150ms transition)
                edge opacity zeroed if either endpoint type is hidden

GraphCanvas unmounts (or d3Data changes again)
        │
        └─► renderer.destroy()
                sim.stop()
                driftTimers.forEach(t => t.stop())
                container.selectAll("*").remove()
                svg zoom and click handlers unbound
```

---

## Why GraphRenderer.js Is Not a React Component

React components re-render in response to state changes. D3 force simulations run continuously
in their own animation loop — `requestAnimationFrame` inside `d3-timer`. If GraphRenderer were
a React component, every Zustand store update (a new retrieval step appearing in the log, the
answer text revealing word-by-word) would trigger a React reconciliation pass. React would diff
the SVG subtree, find that D3 had mutated it, and either overwrite D3's position updates or
trigger a simulation restart.

By keeping GraphRenderer as a plain ES module class instantiated inside a `useRef`, React never
owns the SVG content. The ref is opaque to React — changes to `containerRef.current`'s children
do not appear in React's virtual DOM. D3's tick loop runs uninterrupted at 60fps regardless of
how many times React re-renders the surrounding component tree.

The contract between React and D3 is minimal and explicit:

- React calls `renderer.init()` once when new graph data arrives.
- React calls `renderer.update()` when highlight state changes.
- React calls `renderer.filter()` when visible types change.
- React calls `renderer.destroy()` on cleanup.

Everything else — node positions, link geometry, zoom transform, drag state — belongs to D3
and is never read back into React state.
