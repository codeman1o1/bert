/* eslint-env node */
module.exports = {
	root: true,
	env: {
		browser: true,
		es2021: true
	},
	extends: [
		"eslint:recommended",
		"plugin:@typescript-eslint/recommended",
		"plugin:vue/vue3-recommended",
		"@nuxt/eslint-config",
		"plugin:prettier/recommended"
	],
	parser: "vue-eslint-parser",
	parserOptions: {
		ecmaVersion: "latest",
		parser: "@typescript-eslint/parser",
		sourceType: "module"
	},
	plugins: ["@typescript-eslint", "vue"],
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
}
