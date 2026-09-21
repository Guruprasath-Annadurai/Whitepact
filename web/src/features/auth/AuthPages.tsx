// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { FormEvent, useState } from "react";
import { Eye, EyeOff, LoaderCircle } from "lucide-react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Brand } from "../../components/Brand";
import { Button } from "../../components/Button";
import { Seo } from "../../components/Seo";
import { api } from "../../lib/api";
import { publicAsset } from "../../lib/assets";

function AuthLayout({ children, reversed = false }: { children: React.ReactNode; reversed?: boolean }) {
  const { pathname } = useLocation();
  const titles: Record<string, string> = { "/login": "Sign in", "/signup": "Create account", "/verify-email": "Verify email", "/forgot-password": "Password recovery", "/reset-password": "Reset password" };
  return <><Seo title={`${titles[pathname] ?? "Account"} | WhitePact`} description="Secure access to the WhitePact AI governance workspace." path={pathname} noIndex /><main className={`auth-layout ${reversed ? "auth-layout--reversed" : ""}`}><section className="auth-art"><Brand /><img src={publicAsset("trust-core-head.webp")} alt="" /><h2>The trust layer<br />between<br />AI and action<span>.</span></h2></section><section className="auth-panel">{children}</section></main></>;
}

function PasswordField({ value, onChange, autoComplete }: { value: string; onChange: (value: string) => void; autoComplete: string }) {
  const [visible, setVisible] = useState(false);
  return <label className="field"><span>Password</span><div className="password-field"><input value={value} onChange={(event) => onChange(event.target.value)} type={visible ? "text" : "password"} autoComplete={autoComplete} minLength={12} required /><button type="button" onClick={() => setVisible(!visible)} aria-label={visible ? "Hide password" : "Show password"}>{visible ? <EyeOff /> : <Eye />}</button></div></label>;
}

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const result = await api<{ next: string }>("/api/v1/web/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      const requested = params.get("next");
      navigate(requested && requested.startsWith("/") ? requested : (result.next || "/dashboard"));
    }
    catch (err) { setError(err instanceof Error ? err.message : "Sign in failed"); }
    finally { setBusy(false); }
  }
  return <AuthLayout><Brand /><div className="auth-form"><h1>Welcome back.</h1><p>Manage your agents, policies and governance from one control plane.</p><form onSubmit={submit}><label className="field"><span>Email</span><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required /></label><PasswordField value={password} onChange={setPassword} autoComplete="current-password" />{error && <div className="form-error" role="alert">{error}</div>}<div className="form-links"><Link to="/forgot-password">Forgot password?</Link><Link to="/signup">Create account</Link></div><Button disabled={busy}>{busy ? <><LoaderCircle className="spin" /> Signing in…</> : "Sign in →"}</Button></form></div></AuthLayout>;
}

export function SignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", accepted_terms: false });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const requirements = [form.password.length >= 12, /[a-z]/.test(form.password) && /[A-Z]/.test(form.password), /\d/.test(form.password), /[^A-Za-z0-9]/.test(form.password)];
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { const result = await api<{ verification_url?: string }>("/api/v1/web/auth/register", { method: "POST", body: JSON.stringify(form) }); if (result.verification_url) window.location.assign(result.verification_url); else navigate("/verify-email"); }
    catch (err) { setError(err instanceof Error ? err.message : "Registration failed"); }
    finally { setBusy(false); }
  }
  return <AuthLayout reversed><Brand /><div className="auth-form auth-form--signup"><h1>Create your<br />WhitePact account<span>.</span></h1><p>Your account is verified before an organization or API key can be activated.</p><form onSubmit={submit}><label className="field"><span>Full name</span><input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} autoComplete="name" required /></label><label className="field"><span>Work email</span><input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} autoComplete="email" required /></label><PasswordField value={form.password} onChange={(password) => setForm({ ...form, password })} autoComplete="new-password" /><ul className="password-rules" aria-label="Password requirements">{["At least 12 characters", "Uppercase and lowercase letters", "At least one number", "At least one symbol"].map((rule, i) => <li className={requirements[i] ? "met" : ""} key={rule}>{rule}</li>)}</ul><label className="checkbox"><input type="checkbox" checked={form.accepted_terms} onChange={(e) => setForm({ ...form, accepted_terms: e.target.checked })} required /><span>I agree to the <Link to="/terms" target="_blank">Terms of Service</Link> and acknowledge the <Link to="/privacy" target="_blank">Privacy Policy</Link>.</span></label>{error && <div className="form-error" role="alert">{error}</div>}<Button disabled={busy || requirements.some((item) => !item)}>{busy ? "Creating…" : "Create account →"}</Button></form><p className="auth-foot">Already have an account? <Link to="/login">Sign in</Link></p></div></AuthLayout>;
}

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  async function verify() {
    if (!token) return;
    setState("busy");
    try { await api("/api/v1/web/auth/verify", { method: "POST", body: JSON.stringify({ token }) }); setState("done"); }
    catch (error) { setState("error"); setMessage(error instanceof Error ? error.message : "Verification failed"); }
  }
  return <AuthLayout><Brand /><div className="auth-form"><h1>{state === "done" ? "Email verified." : "Verify your email."}</h1><p>{token ? "Confirm this browser to activate your WhitePact account." : "Check your inbox for a verification link. No API key is issued before email ownership is confirmed."}</p>{state === "error" && <div className="form-error" role="alert">{message}</div>}{state === "done" ? <Button onClick={() => window.location.assign("/login?verified=1")}>Continue to sign in →</Button> : token ? <Button disabled={state === "busy"} onClick={verify}>{state === "busy" ? "Verifying…" : "Verify email →"}</Button> : <Link className="wp-button wp-button--secondary" to="/login">Back to sign in</Link>}</div></AuthLayout>;
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); setState("busy"); setError("");
    try {
      const result = await api<{ reset_url?: string }>("/api/v1/web/auth/password-reset", { method: "POST", body: JSON.stringify({ email }) });
      if (result.reset_url) window.location.assign(result.reset_url);
      else setState("done");
    } catch (err) { setError(err instanceof Error ? err.message : "Password recovery failed"); setState("idle"); }
  }
  return <AuthLayout><Brand /><div className="auth-form"><h1>Password recovery.</h1>{state === "done" ? <><p>If an eligible WhitePact account exists for that address, a one-hour reset link has been sent.</p><Link className="wp-button wp-button--secondary" to="/login">Back to sign in</Link></> : <><p>Enter your verified account email. For privacy, WhitePact returns the same response whether or not an account exists.</p><form onSubmit={submit}><label className="field"><span>Email</span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required /></label>{error && <div className="form-error" role="alert">{error}</div>}<Button disabled={state === "busy"}>{state === "busy" ? "Sending…" : "Send reset link →"}</Button></form><p className="auth-foot"><Link to="/login">Back to sign in</Link></p></>}</div></AuthLayout>;
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const [error, setError] = useState("");
  const requirements = [password.length >= 12, /[a-z]/.test(password) && /[A-Z]/.test(password), /\d/.test(password), /[^A-Za-z0-9]/.test(password)];
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!token) return; setState("busy"); setError("");
    try { await api("/api/v1/web/auth/password-reset/confirm", { method: "POST", body: JSON.stringify({ token, password }) }); setState("done"); }
    catch (err) { setError(err instanceof Error ? err.message : "Password reset failed"); setState("idle"); }
  }
  return <AuthLayout><Brand /><div className="auth-form"><h1>{state === "done" ? "Password updated." : "Set a new password."}</h1>{!token ? <><p>This reset link is incomplete.</p><Link className="wp-button wp-button--secondary" to="/forgot-password">Request a new link</Link></> : state === "done" ? <><p>All existing browser sessions were revoked. Sign in again with your new password.</p><Link className="wp-button" to="/login?reset=1">Continue to sign in →</Link></> : <form onSubmit={submit}><PasswordField value={password} onChange={setPassword} autoComplete="new-password" /><ul className="password-rules" aria-label="Password requirements">{["At least 12 characters", "Uppercase and lowercase letters", "At least one number", "At least one symbol"].map((rule, index) => <li className={requirements[index] ? "met" : ""} key={rule}>{rule}</li>)}</ul>{error && <div className="form-error" role="alert">{error}</div>}<Button disabled={state === "busy" || requirements.some((item) => !item)}>{state === "busy" ? "Updating…" : "Update password →"}</Button></form>}</div></AuthLayout>;
}

export function AcceptInvitationPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  async function accept() {
    if (!token) return;
    setState("busy");
    try {
      const result = await api<{ next?: string }>("/api/v1/web/invitations/accept", { method: "POST", body: JSON.stringify({ token }) });
      setState("done");
      window.location.assign(result.next || "/dashboard");
    } catch (error) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Invitation could not be accepted");
    }
  }
  return <AuthLayout><Brand /><div className="auth-form"><h1>Accept invitation.</h1><p>{token ? "Sign in as the invited email, then accept this membership token. The browser does not grant membership by itself." : "This invitation link is missing a token."}</p>{state === "error" && <div className="form-error" role="alert">{message}</div>}{token ? <Button disabled={state === "busy" || state === "done"} onClick={() => void accept()}>{state === "busy" ? "Accepting…" : "Accept invitation →"}</Button> : <Link className="wp-button wp-button--secondary" to="/login">Sign in</Link>}<p className="auth-foot"><Link to={`/login?next=${encodeURIComponent(`/accept-invitation?token=${token ?? ""}`)}`}>Sign in first</Link></p></div></AuthLayout>;
}
