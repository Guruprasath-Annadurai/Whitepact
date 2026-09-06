// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router-dom";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode; variant?: "primary" | "secondary" | "danger" };

export function Button({ children, className = "", variant = "primary", ...props }: Props) {
  return <button className={`wp-button wp-button--${variant} ${className}`} {...props}>{children}</button>;
}

export function ButtonLink({ to, children, variant = "primary" }: { to: string; children: ReactNode; variant?: "primary" | "secondary" }) {
  return <Link className={`wp-button wp-button--${variant}`} to={to}>{children}</Link>;
}
