import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router";
import { LogoutButton } from "./LogoutButton";
import {
  AskIcon,
  CalculatorIcon,
  DocumentsIcon,
  FilingIcon,
  GuidedIcon,
  HomeIcon,
  ProfileIcon,
  TaxIcon,
  WealthIcon,
} from "./NavIcons";

// The app's navigation (feature 001 FR-027, amended with 006, task T035; design addendum
// 2026-11-11, decision 3). Computers: flat links plus an Account menu. Phones: a bar of four
// groups, Filing and Account opening sheets. New filing pages join FILING; new settings join
// ACCOUNT, so the phone bar stays at four.

type Page = { to: string; label: ReactNode; icon: ReactNode };

const HOME: Page = { to: "/", label: "Home", icon: <HomeIcon /> };
const FILING: Page[] = [
  { to: "/documents", label: "Documents", icon: <DocumentsIcon /> },
  { to: "/tax", label: "Tax", icon: <TaxIcon /> },
  { to: "/calculator", label: "Calculator", icon: <CalculatorIcon /> },
  { to: "/wealth", label: "Wealth statement", icon: <WealthIcon /> },
  { to: "/workflow", label: "Guided filing", icon: <GuidedIcon /> },
];
const ASK: Page = { to: "/ask", label: "Ask", icon: <AskIcon /> };
const ACCOUNT: Page[] = [
  { to: "/profile", label: "Profile", icon: <ProfileIcon /> },
];

type Group = "filing" | "account";

const inGroup = (pages: Page[], path: string) =>
  pages.some((page) => path === page.to || path.startsWith(`${page.to}/`));

/** Which disclosure is open; closes on Escape (focus back to its button), outside clicks and
 * page changes. */
function useDisclosure() {
  const { pathname } = useLocation();
  const [open, setOpen] = useState<Group | null>(null);
  const [shownPath, setShownPath] = useState(pathname);
  const area = useRef<HTMLDivElement | null>(null);
  const buttons = useRef<Partial<Record<Group, HTMLButtonElement | null>>>({});

  // A new page: close whatever was open (React's reset-on-change pattern).
  if (pathname !== shownPath) {
    setShownPath(pathname);
    setOpen(null);
  }

  useEffect(() => {
    if (open === null) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        buttons.current[open]?.focus();
        setOpen(null);
      }
    };
    const onPointer = (event: PointerEvent) => {
      if (!area.current?.contains(event.target as Node)) {
        setOpen(null);
      }
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  const toggle = (group: Group) =>
    setOpen((current) => (current === group ? null : group));
  /** Remembers a group's button, so Escape can put focus back on it. */
  const buttonFor = (group: Group) => (element: HTMLButtonElement | null) => {
    buttons.current[group] = element;
  };
  return { open, toggle, area, buttonFor, pathname };
}

function PageLink({ page, children }: { page: Page; children?: ReactNode }) {
  return (
    <NavLink to={page.to} end={page.to === "/"}>
      {children ?? (
        <>
          {page.icon}
          <span>{page.label}</span>
        </>
      )}
    </NavLink>
  );
}

/** The list inside the Account menu or sheet: its pages, then Log out. */
function AccountItems() {
  return (
    <ul>
      {ACCOUNT.map((page) => (
        <li key={page.to}>
          <PageLink page={page} />
        </li>
      ))}
      <li className="logout">
        <LogoutButton />
      </li>
    </ul>
  );
}

/** Computers: the main pages as links. */
export function ComputerLinks() {
  return (
    <nav className="app-nav" aria-label="Main">
      <ul>
        {[HOME, ...FILING, ASK].map((page) => (
          <li key={page.to}>
            <PageLink page={page}>
              <span>{page.label}</span>
            </PageLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Computers: the Account menu at the end of the header (Profile, Log out). */
export function AccountMenu() {
  const { open, toggle, area, buttonFor, pathname } = useDisclosure();
  return (
    <div className="account" ref={area}>
      <button
        type="button"
        className="account-button"
        aria-expanded={open === "account"}
        aria-controls="account-menu"
        aria-current={inGroup(ACCOUNT, pathname) ? "true" : undefined}
        ref={buttonFor("account")}
        onClick={() => toggle("account")}
      >
        <ProfileIcon />
        <span>Account</span>
      </button>
      {open === "account" && (
        <div id="account-menu" className="menu-panel">
          <AccountItems />
        </div>
      )}
    </div>
  );
}

/** Phones: a bar of four along the bottom; Filing and Account open sheets above it. */
export function PhoneNav() {
  const { open, toggle, area, buttonFor, pathname } = useDisclosure();

  const groupButton = (
    group: Group,
    label: string,
    icon: ReactNode,
    pages: Page[],
  ) => (
    <button
      type="button"
      aria-expanded={open === group}
      aria-controls={`${group}-sheet`}
      aria-current={inGroup(pages, pathname) ? "true" : undefined}
      ref={buttonFor(group)}
      onClick={() => toggle(group)}
    >
      {icon}
      <span>{label}</span>
    </button>
  );

  return (
    <div ref={area}>
      {open !== null && <div className="sheet-backdrop" aria-hidden="true" />}
      {open === "filing" && (
        <div
          id="filing-sheet"
          className="sheet"
          role="group"
          aria-label="Filing"
        >
          <ul>
            {FILING.map((page) => (
              <li key={page.to}>
                <PageLink page={page} />
              </li>
            ))}
          </ul>
        </div>
      )}
      {open === "account" && (
        <div
          id="account-sheet"
          className="sheet"
          role="group"
          aria-label="Account"
        >
          <AccountItems />
        </div>
      )}
      <nav className="app-nav" aria-label="Main">
        <ul>
          <li>
            <PageLink page={HOME} />
          </li>
          <li>{groupButton("filing", "Filing", <FilingIcon />, FILING)}</li>
          <li>
            <PageLink page={ASK} />
          </li>
          <li>{groupButton("account", "Account", <ProfileIcon />, ACCOUNT)}</li>
        </ul>
      </nav>
    </div>
  );
}
