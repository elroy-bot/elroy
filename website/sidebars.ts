import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docs: [
    'index',
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
};

export default sidebars;
