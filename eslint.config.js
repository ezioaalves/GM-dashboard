import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

export default [
  { ignores: ["dist", "node_modules", "frontend/e2e"] }, js.configs.recommended, ...tseslint.configs.recommended,
  { files: ["frontend/src/**/*.{ts,tsx}"], plugins: { "react-hooks": reactHooks }, rules: { ...reactHooks.configs.recommended.rules, "no-restricted-globals": ["error", { name: "fetch", message: "Use the typed api facade." }] } },
  { files: ["frontend/src/lib/api.ts"], rules: { "no-restricted-globals": "off" } },
  { files: ["frontend/src/ui/**/*.{ts,tsx}", "frontend/src/features/**/*.{ts,tsx}", "frontend/src/navigation.tsx", "frontend/src/pages/Ideas.tsx"], rules: { "no-restricted-syntax": ["error", { selector: "JSXAttribute[name.name='style']", message: "Use the feature stylesheet instead of inline styles." }] } },
];
