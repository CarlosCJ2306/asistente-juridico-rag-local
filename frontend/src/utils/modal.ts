export function modalDismissProps(pending: boolean):
  | { readonly preventClose: true; readonly preventCloseReason: string }
  | { readonly preventClose: false } {
  return pending
    ? { preventClose: true, preventCloseReason: "Espera a que finalice la operación." }
    : { preventClose: false };
}
