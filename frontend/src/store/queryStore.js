import { create } from "zustand";

const useQueryStore = create((set, get) => ({
  question:   "",
  isQuerying: false,
  steps:      [],
  answer:     null,
  error:      null,
  history:    [],

  setQuestion: (q) => set({ question: q }),

  startQuery: () => set({ isQuerying: true, steps: [], answer: null, error: null }),

  addStep: (event) => set((state) => ({ steps: [...state.steps, event] })),

  setAnswer: (data) =>
    set((state) => ({
      answer:     data,
      isQuerying: false,
      history: [
        ...state.history,
        { question: state.question, answer: data, timestamp: Date.now() },
      ],
    })),

  setError: (msg) => set({ error: msg, isQuerying: false }),

  clearHistory: () => set({ steps: [], answer: null, error: null, isQuerying: false, question: "", history: [] }),
}));

export default useQueryStore;
