import { queryClient } from "../../lib/queryClient.ts";

export function clearAuthSession(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  queryClient.clear();
}
