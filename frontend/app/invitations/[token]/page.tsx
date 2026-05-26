"use client";

import { use, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle, Mail, Building, Shield, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

interface InvitationDetails {
  organization_id: string;
  organization_name: string;
  email: string;
  role: string;
  invited_by: string;
  expires_at: string;
  status: string;
}

export default function AcceptInvitationPage({ params }: { params: Promise<{ token: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const [invitation, setInvitation] = useState<InvitationDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isNewUser, setIsNewUser] = useState(false);
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");

  const fetchInvitation = useCallback(async () => {
    try {
      // Get invitation details
      const response = await fetch(`/api/v1/invitations/${resolvedParams.token}`);

      if (response.ok) {
        const data = await response.json();
        setInvitation(data);
        setIsNewUser(!data.user_exists);
      } else if (response.status === 404) {
        setError("This invitation link is invalid or has expired.");
      } else if (response.status === 400) {
        const errorData = await response.json();
        setError(errorData.detail || "This invitation cannot be accepted.");
      } else {
        setError("Failed to load invitation details.");
      }
    } catch {
      setError("An error occurred while loading the invitation.");
    } finally {
      setLoading(false);
    }
  }, [resolvedParams.token]);

  useEffect(() => {
    fetchInvitation();
  }, [fetchInvitation]);

  const handleAccept = async () => {
    if (isNewUser) {
      if (!fullName.trim()) {
        toast.error("Please enter your full name");
        return;
      }
      if (password.length < 8) {
        toast.error("Password must be at least 8 characters");
        return;
      }
      if (password !== passwordConfirm) {
        toast.error("Passwords do not match");
        return;
      }
    }

    setAccepting(true);
    try {
      const response = await fetch(`/api/v1/invitations/${resolvedParams.token}/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: isNewUser ? fullName : undefined,
          password: isNewUser ? password : undefined,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        toast.success(data.message || "Invitation accepted successfully!");

        // Redirect to login or dashboard
        setTimeout(() => {
          if (isNewUser) {
            router.push("/login");
          } else {
            router.push("/dashboard");
          }
        }, 2000);
      } else {
        const errorData = await response.json();
        toast.error(errorData.detail || "Failed to accept invitation");
      }
    } catch {
      toast.error("An error occurred");
    } finally {
      setAccepting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/30">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/30 p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-red-100">
              <Mail className="h-10 w-10 text-red-600" />
            </div>
            <CardTitle>Invalid Invitation</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardFooter>
            <Button className="w-full" onClick={() => router.push("/")}>
              Return to Home
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  if (!invitation) {
    return null;
  }

  const getRoleBadgeColor = (role: string) => {
    switch (role.toLowerCase()) {
      case "admin":
        return "bg-[#5B8DBE] text-white border-[#5B8DBE]";
      default:
        return "bg-[#2D3748] text-white border-[#2D3748]";
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#FAFAFA] via-[#F5F5F7] to-[#EEEEEE] p-4">
      <Card className="w-full max-w-md shadow-lg border-gray-200">
        <CardHeader className="text-center pb-6">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-xl bg-[#2D3748] shadow-sm">
            <Mail className="h-8 w-8 text-white" strokeWidth={1.5} />
          </div>
          <CardTitle className="text-3xl font-light text-[#2D3748]">
            <span className="font-normal">You&apos;re</span> Invited!
          </CardTitle>
          <CardDescription className="text-[#6B7280] font-light mt-2">
            {invitation.invited_by} has invited you to join their organization
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Invitation Details */}
          <div className="rounded-lg border bg-muted/50 p-4">
            <div className="flex items-center gap-3 mb-3">
              <Building className="h-5 w-5 text-muted-foreground" />
              <div>
                <div className="font-semibold">{invitation.organization_name}</div>
                <div className="text-sm text-muted-foreground">Organization</div>
              </div>
            </div>
            <div className="flex items-center gap-3 mb-3">
              <Mail className="h-5 w-5 text-muted-foreground" />
              <div>
                <div className="font-medium">{invitation.email}</div>
                <div className="text-sm text-muted-foreground">Your email</div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Shield className="h-5 w-5 text-muted-foreground" />
              <div className="flex items-center gap-2">
                <Badge variant="outline" className={getRoleBadgeColor(invitation.role)}>
                  {invitation.role}
                </Badge>
                <span className="text-sm text-muted-foreground">access level</span>
              </div>
            </div>
          </div>

          {/* New User Form */}
          {isNewUser && (
            <div className="space-y-4">
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                <p className="text-sm text-blue-900">
                  <strong>New to the platform?</strong> Create your account to accept this
                  invitation.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="fullName">Full Name</Label>
                <Input
                  id="fullName"
                  placeholder="John Doe"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    minLength={8}
                  />
                  <p className="text-xs text-muted-foreground">
                    Min. 8 chars with uppercase, lowercase & digit
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="passwordConfirm">Confirm Password</Label>
                  <Input
                    id="passwordConfirm"
                    type="password"
                    placeholder="••••••••"
                    value={passwordConfirm}
                    onChange={(e) => setPasswordConfirm(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Re-enter your password
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Existing User Info */}
          {!isNewUser && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-3">
              <p className="text-sm text-green-900">
                <CheckCircle className="inline h-4 w-4 mr-1" />
                You&apos;ll be added to this organization with your existing account.
              </p>
            </div>
          )}

          {/* Benefits */}
          <div>
            <h4 className="font-semibold mb-2">What you&apos;ll get:</h4>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 mt-0.5 text-green-600 flex-shrink-0" />
                Access to organization&apos;s leaflets and data
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 mt-0.5 text-green-600 flex-shrink-0" />
                Upload and process new leaflets
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 mt-0.5 text-green-600 flex-shrink-0" />
                Collaborate with team members
              </li>
              {invitation.role.toLowerCase() === "admin" && (
                <li className="flex items-start gap-2">
                  <CheckCircle className="h-4 w-4 mt-0.5 text-green-600 flex-shrink-0" />
                  Manage team members and settings
                </li>
              )}
            </ul>
          </div>
        </CardContent>

        <CardFooter className="flex flex-col gap-3">
          <Button className="w-full" onClick={handleAccept} disabled={accepting}>
            {accepting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Accepting...
              </>
            ) : (
              <>
                <CheckCircle className="mr-2 h-4 w-4" />
                Accept Invitation
              </>
            )}
          </Button>
          <p className="text-xs text-center text-muted-foreground">
            By accepting, you agree to the terms of service
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
