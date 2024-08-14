// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
	modules: ["@nuxtjs/tailwindcss", "@nuxt/eslint"],
	devtools: { enabled: true },
	routeRules: {
		"/github": {
			redirect: "https://github.com/codeman1o1/bert"
		}
	},
	devServer: {
		port: 6969
	}
})
