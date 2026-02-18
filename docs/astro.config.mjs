// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightThemeObsidian from 'starlight-theme-obsidian'
import mermaid from 'astro-mermaid';

// https://astro.build/config
export default defineConfig({
	redirects: {
		'/': '/basic/'
	},
	integrations: [
		mermaid({
			theme: 'forest',
			autoTheme: true
		}),
		starlight({
			title: 'MD-Models',
			social: [
				{
					icon: 'github',
					label: 'GitHub',
					href: 'https://github.com/FairCHemistry/py-mdmodels'
				}
			],
			customCss: [
				'./src/styles/styles.css',
			],
			plugins: [
				starlightThemeObsidian(
					{
						backlinks: false,
						graph: false
					}
				)
			],
			sidebar: [
				{ label: 'Introduction', slug: 'basic' },
				{ label: 'Installation', slug: 'installation' },
				{
					label: 'Usage',
					items: [
						{ label: 'Parsing Markdown', slug: 'basic/parsing' },
						{ label: 'Using the Library container', slug: 'basic/library' },
						{ label: 'Creating and Working with Data', slug: 'basic/creating-data' },
						{ label: 'Validating Data', slug: 'basic/validation' },
						{ label: 'Serializing Data', slug: 'basic/serialization' },
						{ label: 'Converting Formats', slug: 'basic/converting-formats' },
						{ label: 'Querying Data', slug: 'basic/querying' },
						{ label: 'Working with Multiple Models', slug: 'basic/multiple-models' },
					],
				},
				{
					label: 'Databases',
					items: [
						{ label: 'Relational Databases', slug: 'databases/sql' },
						{ label: 'Graph Databases', slug: 'databases/graphdb' },
						{ label: 'Vector Databases', slug: 'databases/vector' },
					],
				},
				{
					label: 'Integrations',
					items: [
						{
							label: 'CLI Configuration',
							slug: 'integrations/cli',
							badge: 'New',
						},
						{
							label: 'FastMCP',
							slug: 'integrations/fastmcp',
							badge: 'New',
						},
						{
							label: 'GraphQL',
							slug: 'integrations/graphql',
							badge: 'New',
						},
						{
							label: 'FastAPI',
							slug: 'integrations/fastapi',
							badge: 'New',
						},
					],
				},
			],
		}),]
});
