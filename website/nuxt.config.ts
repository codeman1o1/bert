// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
	compatibilityDate: "2024-04-03",
	modules: ["@nuxtjs/tailwindcss", "@nuxt/eslint"],
	devtools: { enabled: true },
	routeRules: {
		"/github": {
			redirect: "https://github.com/codeman1o1/bert"
		}
	},
	typescript: {
		typeCheck: true
	},
	devServer: {
		port: 6969
	}
})
