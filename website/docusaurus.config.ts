import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'Elroy',
  tagline: 'An AI memory and reminder assistant',
  favicon: 'img/logo_circle.png',

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Set the production url of your site here
  url: 'https://elroy.bot',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'elroy-bot', // Usually your GitHub org/user name.
  projectName: 'elroy', // Usually your repo name.

  onBrokenLinks: 'warn',

  markdown: {
    format: 'detect',
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  // CRITICAL: This maintains .html URLs to match MkDocs behavior
  trailingSlash: false,

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  plugins: [
    [
      '@docusaurus/plugin-client-redirects',
      {
        createRedirects(existingPath) {
          // For any path, create a .html redirect
          // e.g., /installation -> /installation.html
          if (existingPath.includes('/blog/') || existingPath === '/blog') {
            return undefined; // Don't create .html redirects for blog
          }
          return [`${existingPath}.html`];
        },
      },
    ],
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/', // Serve docs at the site's root
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/elroy-bot/elroy/edit/main/docs/',
        },
        blog: {
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            copyright: 'Copyright © 2025 Elroy Team',
            title: 'Elroy Blog',
            description: 'Thoughts on AI memory and automation',
          },
          editUrl: 'https://github.com/elroy-bot/elroy/edit/main/docs/',
          blogTitle: 'Elroy Blog',
          blogDescription: 'Thoughts on AI memory and automation',
          postsPerPage: 'ALL',
          blogSidebarCount: 0, // Disable separate blog sidebar
          onUntruncatedBlogPosts: 'ignore',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
        gtag: process.env.NODE_ENV === 'production' ? {
          trackingID: 'G-WGS6XZX78T',
          anonymizeIP: true,
        } : false,
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/logo_circle.png',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Elroy',
      logo: {
        alt: 'Elroy Logo',
        src: 'img/logo_circle.png',
      },
      items: [
        {
          type: 'doc',
          docId: 'how_it_works',
          position: 'left',
          label: 'How It Works',
        },
        {
          type: 'doc',
          docId: 'installation',
          position: 'left',
          label: 'Installation',
        },
        {
          type: 'doc',
          docId: 'configuration/index',
          position: 'left',
          label: 'Configuration',
        },
        {to: '/blog', label: 'Blog', position: 'left'},
        {
          href: '/blog/rss.xml',
          label: 'RSS',
          position: 'left',
        },
        {
          href: 'https://github.com/elroy-bot/elroy',
          label: 'GitHub',
          position: 'right',
        },
        {
          href: 'https://discord.gg/5PJUY4eMce',
          label: 'Discord',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Community',
          items: [
            {
              label: 'Discord',
              href: 'https://discord.gg/5PJUY4eMce',
            },
            {
              label: 'GitHub',
              href: 'https://github.com/elroy-bot/elroy',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Elroy Team`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
