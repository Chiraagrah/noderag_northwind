import useQueryStore from "../store/queryStore";
import useGraphStore from "../store/graphStore";
import { queryStream } from "../utils/api";

export function useQueryStream() {
  const startQuery    = useQueryStore(s => s.startQuery);
  const addStep       = useQueryStore(s => s.addStep);
  const setAnswer     = useQueryStore(s => s.setAnswer);
  const setError      = useQueryStore(s => s.setError);
  const setHighlights = useGraphStore(s => s.setHighlights);

  const submitQuery = async (question, top_k = 10) => {
    if (!question.trim()) return;
    startQuery();
    const startTime = Date.now();

    try {
      for await (const event of queryStream(question, top_k)) {
        const stamped = { ...event, _elapsed: Date.now() - startTime };
        addStep(stamped);

        if (event.event_type === "ppr") {
          const ids = new Set((event.data.nodes ?? []).map(n => n.node_id));
          setHighlights(ids);
        }
        if (event.event_type === "answer") setAnswer(event.data);
        if (event.event_type === "error")  setError(event.data.message);
      }
    } catch (err) {
      setError(err.message ?? "Stream error");
    }
  };

  return { submitQuery };
}
