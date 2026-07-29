import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: [
                "../../chat/*",
                "../../chat/**",
                "../../documents/*",
                "../../documents/**",
                "../../hpn-matrices/*",
                "../../hpn-matrices/**",
                "../../legal-network/*",
                "../../legal-network/**",
                "../../models/*",
                "../../models/**",
              ],
              message: "Importa otra feature únicamente desde su index.ts público.",
            },
            {
              group: ["**/design-system/internal", "**/design-system/internal/**"],
              message: "El Design System solo se consume desde su fachada pública.",
            },
          ],
        },
      ],
    },
  },
);
