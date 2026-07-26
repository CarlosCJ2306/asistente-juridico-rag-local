import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../composites.module.css";

export interface TabItem {
  id: string;
  label: ReactNode;
  content: ReactNode;
  disabled?: boolean;
}

export interface TabsProps {
  items: ReadonlyArray<TabItem>;
  activeId?: string;
  defaultActiveId?: string;
  onChange?: (id: string) => void;
  orientation?: "horizontal" | "vertical";
  activation?: "automatic" | "manual";
  label: string;
  className?: string;
}

export function Tabs({ items, activeId, defaultActiveId, onChange, orientation = "horizontal", activation = "automatic", label, className }: TabsProps) {
  const baseId = useId();
  const firstEnabled = useMemo(() => items.find((item) => !item.disabled)?.id ?? "", [items]);
  const [internalId, setInternalId] = useState(defaultActiveId ?? firstEnabled);
  const selectedId = activeId ?? internalId;
  const [focusedId, setFocusedId] = useState(defaultActiveId ?? firstEnabled);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const aliasesRef = useRef({ next: 0, byItemId: new Map<string, string>() });

  useEffect(() => {
    if (activeId && items.some((item) => item.id === activeId && !item.disabled)) {
      setFocusedId(activeId);
    }
  }, [activeId, items]);

  const getAlias = (itemId: string) => {
    const existing = aliasesRef.current.byItemId.get(itemId);
    if (existing) return existing;
    const alias = `item-${aliasesRef.current.next}`;
    aliasesRef.current.next += 1;
    aliasesRef.current.byItemId.set(itemId, alias);
    return alias;
  };

  const select = (id: string) => {
    if (!items.some((item) => item.id === id && !item.disabled)) return;
    if (activeId === undefined) setInternalId(id);
    setFocusedId(id);
    onChange?.(id);
  };

  const moveFocus = (currentIndex: number, direction: 1 | -1, selectOnFocus: boolean) => {
    if (items.length === 0) return;
    for (let step = 1; step <= items.length; step += 1) {
      const index = (currentIndex + direction * step + items.length) % items.length;
      if (!items[index]?.disabled) {
        setFocusedId(items[index].id);
        tabRefs.current[index]?.focus();
        if (selectOnFocus) select(items[index].id);
        return;
      }
    }
  };

  const focusBoundary = (fromEnd: boolean) => {
    const indices = items.map((_, index) => index);
    if (fromEnd) indices.reverse();
    const index = indices.find((candidate) => !items[candidate]?.disabled);
    if (index !== undefined) {
      setFocusedId(items[index].id);
      tabRefs.current[index]?.focus();
      if (activation === "automatic") select(items[index].id);
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number, id: string) => {
    const previousKey = orientation === "horizontal" ? "ArrowLeft" : "ArrowUp";
    const nextKey = orientation === "horizontal" ? "ArrowRight" : "ArrowDown";
    if (event.key === previousKey || event.key === nextKey) {
      event.preventDefault();
      moveFocus(index, event.key === nextKey ? 1 : -1, activation === "automatic");
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      focusBoundary(event.key === "End");
    } else if (activation === "manual" && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      select(id);
    }
  };

  const selected = items.find((item) => item.id === selectedId && !item.disabled) ?? items.find((item) => !item.disabled);
  const rovingId = items.some((item) => item.id === focusedId && !item.disabled)
    ? focusedId
    : selected?.id ?? "";

  return (
    <div className={classNames(styles.tabs, className)}>
      <div role="tablist" aria-label={label} aria-orientation={orientation} className={classNames(styles.tabList, orientation === "vertical" && styles.tabListVertical)}>
        {items.map((item, index) => {
          const isSelected = item.id === selected?.id;
          const alias = getAlias(item.id);
          const tabId = `${baseId}-tab-${alias}`;
          const panelId = `${baseId}-panel-${alias}`;
          return (
            <button key={item.id} ref={(node) => { tabRefs.current[index] = node; }} id={tabId} type="button" role="tab" aria-selected={isSelected} aria-controls={panelId} tabIndex={item.id === rovingId ? 0 : -1} disabled={item.disabled} className={classNames(styles.tab, isSelected && styles.tabSelected)} onClick={() => select(item.id)} onFocus={() => setFocusedId(item.id)} onKeyDown={(event) => handleKeyDown(event, index, item.id)}>
              {item.label}
            </button>
          );
        })}
      </div>
      {selected ? (() => {
        const alias = getAlias(selected.id);
        return <div id={`${baseId}-panel-${alias}`} role="tabpanel" aria-labelledby={`${baseId}-tab-${alias}`} tabIndex={0} className={styles.tabPanel}>{selected.content}</div>;
      })() : null}
    </div>
  );
}
