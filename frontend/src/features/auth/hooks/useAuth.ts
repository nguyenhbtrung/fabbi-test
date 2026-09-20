import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useLogout, fetchCurrentUser } from "../api/auth";
import { clearAuthSession } from "../session";

export function useAuth() {
  const navigate = useNavigate();
  const logoutMutation = useLogout();

  const token = localStorage.getItem("access_token");
  const hasToken = Boolean(token);

  const {
    data: user,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["currentUser"],
    queryFn: fetchCurrentUser,
    enabled: hasToken,
    retry: false,
  });

  const isAuthenticated = Boolean(user) && !error;

  const logout = () => {
    logoutMutation.mutate(undefined, {
      onSuccess: () => {
        clearAuthSession();
        navigate("/login");
      },
      onError: () => {
        // Even on error, clear local tokens and query cache before redirecting
        clearAuthSession();
        navigate("/login");
      },
    });
  };

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    logout,
  };
}
