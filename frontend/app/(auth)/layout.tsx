import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/actions/auth";

export default async function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getCurrentUser();

  if (user) {
    redirect("/dashboard");
  }

  return (
    <div className="min-h-screen bg-white">
      {children}
    </div>
  );
}
