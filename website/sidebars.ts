import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docs: [
    {
      type: 'category',
      label: 'Elroy',
      collapsed: false,
      items: [
        {
          type: 'doc',
          id: 'index',
          label: 'Home',
        },
        'how_it_works',
        'installation',
        'cli',
        {
          type: 'category',
          label: 'Configuration',
          items: [
            'configuration/index',
            'configuration/basic',
            'configuration/models',
            'configuration/context',
            'configuration/memory',
            'configuration/tracing',
            'configuration/ui',
          ],
        },
        'scripting',
        {
          type: 'category',
          label: 'Tools',
          items: [
            'tools_guide',
            'tools_schema',
          ],
        },
      ],
    },
    {
      type: 'category',
      label: 'Blog',
      collapsed: false,
      items: [
        {
          type: 'link',
          label: 'All Posts',
          href: '/blog',
        },
        {
          type: 'link',
          label: 'AI is a Floor Raiser, not a Ceiling Raiser',
          href: '/blog/2025/11/22/ai-is-a-floor-raiser',
        },
        {
          type: 'link',
          label: 'Yes or No, Please',
          href: '/blog/2025/11/17/yes-or-no-please',
        },
        {
          type: 'link',
          label: 'Tack - Reminders powered by local AI',
          href: '/blog/2025/11/14/tack',
        },
        {
          type: 'link',
          label: 'Make It Easy for Humans First, Then AI',
          href: '/blog/2025/11/09/make-it-easy-for-humans',
        },
        {
          type: 'link',
          label: 'Optimizing repos for AI',
          href: '/blog/2025/11/03/optimizing-repos-for-ai',
        },
        {
          type: 'link',
          label: 'Add Autonomy Last',
          href: '/blog/2025/07/07/autonomy-last',
        },
        {
          type: 'link',
          label: 'RSS Feed',
          href: '/blog/rss.xml',
        },
      ],
    },
  ],
};

export default sidebars;
