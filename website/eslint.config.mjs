import eslintPluginPrettier from "eslint-plugin-prettier/recommended"
import withNuxt from "./.nuxt/eslint.config.mjs"

export default withNuxt(eslintPluginPrettier, {
	rules: {
		"vue/multi-word-component-names": "off",
		"@typescript-eslint/no-unused-vars": [
			"warn",
			{
				varsIgnorePattern: "^_",
				argsIgnorePattern: "^_"
			}
		]
	}
})
