import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { getBreadcrumbs, getSectionTitle, getVisibleNavigationSections } from "../../app/navigation/navigation.utils";
import { NavigationGroup, SkipLink } from "../../components";
import { Drawer } from "../../design-system";
import { AppSidebar } from "../AppSidebar/AppSidebar";
import { AppTopbar } from "../AppTopbar/AppTopbar";
import { MainContent } from "../MainContent/MainContent";
import styles from "../layouts.module.css";

const MAIN_CONTENT_ID = "main-content";
const MOBILE_NAVIGATION_ID = "mobile-navigation";
const DESKTOP_NAVIGATION_QUERY = "(min-width: 64rem)";

export function AppLayout() {
  const location = useLocation();
  const [sidebarCompact, setSidebarCompact] = useState(false);
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const sections = getVisibleNavigationSections();
  const sectionTitle = getSectionTitle(location.pathname);
  const breadcrumbs = getBreadcrumbs(location.pathname);
  const fullBleed = location.pathname === "/chat" || location.pathname.startsWith("/chat/");

  useEffect(() => {
    const desktopNavigation = window.matchMedia(DESKTOP_NAVIGATION_QUERY);
    const closeMobileNavigation = (event: MediaQueryListEvent) => {
      if (event.matches) setMobileNavigationOpen(false);
    };
    desktopNavigation.addEventListener("change", closeMobileNavigation);
    return () => desktopNavigation.removeEventListener("change", closeMobileNavigation);
  }, []);

  return (
    <div className={[styles.appLayout, sidebarCompact ? styles.appLayoutCompact : null, fullBleed ? styles.appLayoutFullBleed : null].filter(Boolean).join(" ")}>
      <SkipLink targetId={MAIN_CONTENT_ID} />
      <AppSidebar sections={sections} compact={sidebarCompact} onCompactChange={setSidebarCompact} />
      <AppTopbar
        sectionTitle={sectionTitle}
        onOpenNavigation={() => setMobileNavigationOpen(true)}
        navigationOpen={mobileNavigationOpen}
        navigationId={MOBILE_NAVIGATION_ID}
      />
      <MainContent id={MAIN_CONTENT_ID} breadcrumbs={breadcrumbs} fullBleed={fullBleed}><Outlet /></MainContent>
      <Drawer id={MOBILE_NAVIGATION_ID} open={mobileNavigationOpen} onOpenChange={setMobileNavigationOpen} title="Navegación principal" position="start">
        <nav className={styles.mobileNavigation} aria-label="Navegación principal móvil">
          {sections.map((section) => (
            <NavigationGroup key={section.id} section={section} onNavigate={() => setMobileNavigationOpen(false)} />
          ))}
        </nav>
      </Drawer>
    </div>
  );
}
