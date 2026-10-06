// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useRef, useState } from "react";
import { Menu, X } from "lucide-react";
import { NavLink } from "react-router-dom";
import { Brand } from "./Brand";

const corporateLinks = [
  ["Product", "/product"], ["Architecture", "/architecture"],
  ["Developers", "/developers"], ["Security", "/security"],
  ["Enterprise", "/enterprise"], ["Docs", "/docs"], ["Company", "/about"],
] as const;

export function CorporateNav() {
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const navigation = useRef<HTMLElement>(null);
  const focusFrame = useRef<number | undefined>(undefined);
  function close(restore = false) {
    if (focusFrame.current !== undefined) cancelAnimationFrame(focusFrame.current);
    focusFrame.current = undefined;
    setOpen(false);
    if (restore) toggle.current?.focus();
  }
  return <>
    <a className="corporate-skip" href="#main-content">Skip to main content</a>
    <header className="corporate-nav" onKeyDown={(event) => {
      if (event.key === "Escape" && open) { event.preventDefault(); close(true); }
    }}>
      <Brand optimized />
      <button ref={toggle} className="corporate-toggle" aria-expanded={open} aria-controls="corporate-navigation" aria-label={open ? "Close menu" : "Open menu"} onClick={() => {
        if (open) close(true);
        else { setOpen(true); focusFrame.current = requestAnimationFrame(() => { focusFrame.current = undefined; navigation.current?.querySelector<HTMLAnchorElement>("a")?.focus(); }); }
      }}>{open ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}</button>
      <nav ref={navigation} id="corporate-navigation" className={open ? "is-open" : ""} aria-label="Primary navigation">
        {corporateLinks.map(([label, path]) => <NavLink key={path} to={path} onClick={() => close()}>{label}</NavLink>)}
        <a href="https://github.com/Guruprasath-Annadurai/Whitepact" onClick={() => close()}>GitHub</a>
        <NavLink className="wp-button wp-button--primary" to="/docs" onClick={() => close()}>Start locally</NavLink>
      </nav>
    </header>
  </>;
}
