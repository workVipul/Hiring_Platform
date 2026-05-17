"use client";

import { useEffect, useState } from "react";

import { jdApi } from "@/services/jdApi";
import type { JD } from "@/types/jd";

export function useJDs() {
  const [jds, setJDs] = useState<JD[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await jdApi.list();
      setJDs(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load JDs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Data loading is the external sync point for this hook.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, []);

  return { jds, total, loading, error, reload: load, setJDs, setTotal };
}
