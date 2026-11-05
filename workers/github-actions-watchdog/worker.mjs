import { monitorGitHubActions } from "./service.mjs";

export default {
  async scheduled(event, env) {
    const scheduledAt = new Date(event.scheduledTime).toISOString();
    try {
      const results = await monitorGitHubActions(env);
      console.log(JSON.stringify({ event: "github-actions-watchdog", scheduledAt, results }));
    } catch (error) {
      console.error(JSON.stringify({
        event: "github-actions-watchdog-error",
        scheduledAt,
        message: error?.message || String(error),
        results: error?.results || [],
      }));
      throw error;
    }
  },
};
