export type ApiQueryValue = string | number | boolean;

export type ApiQuery = Readonly<Record<string, ApiQueryValue | readonly ApiQueryValue[] | null | undefined>>;

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | { readonly [key: string]: JsonValue } | readonly JsonValue[];

export type ResponseParser<T> = (value: unknown) => T;

export interface ApiResponse<T> {
  readonly data: T | null;
  readonly status: number;
}

export interface ApiRequestOptions {
  readonly query?: ApiQuery;
  readonly signal?: AbortSignal;
  readonly timeoutMs?: number;
}
