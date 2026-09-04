export function logout(router: { push: (path: string) => void }) {
  localStorage.removeItem("token");
  router.push("/login");
}