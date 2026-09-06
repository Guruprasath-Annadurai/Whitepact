// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { Seo } from "./components/Seo";
import { HomePage } from "./features/marketing/HomePage";
import { AboutPage, BillingResultPage, ContactPage, DocsPage, LegalPage, NotFoundPage, TrustCenterPage } from "./features/marketing/PublicPages";

const LoginPage = lazy(() => import("./features/auth/AuthPages").then((module) => ({ default: module.LoginPage })));
const SignupPage = lazy(() => import("./features/auth/AuthPages").then((module) => ({ default: module.SignupPage })));
const VerifyEmailPage = lazy(() => import("./features/auth/AuthPages").then((module) => ({ default: module.VerifyEmailPage })));
const ForgotPasswordPage = lazy(() => import("./features/auth/AuthPages").then((module) => ({ default: module.ForgotPasswordPage })));
const ResetPasswordPage = lazy(() => import("./features/auth/AuthPages").then((module) => ({ default: module.ResetPasswordPage })));
const OnboardingPage = lazy(() => import("./features/onboarding/OnboardingPage").then((module) => ({ default: module.OnboardingPage })));
const DashboardShell = lazy(() => import("./features/dashboard/DashboardShell").then((module) => ({ default: module.DashboardShell })));
const OverviewPage = lazy(() => import("./features/dashboard/OverviewPage").then((module) => ({ default: module.OverviewPage })));
const ApiKeysPage = lazy(() => import("./features/api-keys/ApiKeysPage").then((module) => ({ default: module.ApiKeysPage })));
const DomainPage = lazy(() => import("./features/dashboard/DomainPage").then((module) => ({ default: module.DomainPage })));

export default function App() {
  return (
    <Suspense fallback={<div className="app-loading"><span>Loading WhitePact</span></div>}><Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/contact" element={<ContactPage />} />
      <Route path="/docs" element={<DocsPage />} />
      <Route path="/trust" element={<TrustCenterPage />} />
      <Route path="/terms" element={<LegalPage kind="terms" />} />
      <Route path="/privacy" element={<LegalPage kind="privacy" />} />
      <Route path="/billing/success" element={<BillingResultPage result="success" />} />
      <Route path="/billing/cancelled" element={<BillingResultPage result="cancelled" />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/onboarding" element={<><Seo title="Create workspace | WhitePact" description="Create an organization-bound WhitePact workspace." path="/onboarding" noIndex /><OnboardingPage /></>} />
      <Route path="/dashboard" element={<><Seo title="Workspace | WhitePact" description="Authenticated WhitePact AI governance workspace." path="/dashboard" noIndex /><DashboardShell /></>}>
        <Route index element={<OverviewPage />} />
        <Route path="api-keys" element={<ApiKeysPage />} />
        <Route path=":domain" element={<DomainPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes></Suspense>
  );
}
