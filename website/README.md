# Elroy Documentation Site

This directory contains the Docusaurus-based documentation site for Elroy, migrated from MkDocs while maintaining all existing URLs.

## Quick Start

```bash
# Install dependencies
npm install

# Start development server (opens browser at http://localhost:3000)
npm start

# Build for production
npm run build

# Serve production build locally
npm run serve
```

## Using Just

If you have [just](https://github.com/casey/just) installed, you can use these commands from the project root:

```bash
just docs          # Start dev server
just docs-build    # Build site
just docs-serve    # Serve built site
```

## Project Structure

```
website/
├── blog/                      # Blog posts (YYYY-MM-DD-slug.md format)
├── docs/                      # Documentation markdown files
├── src/
│   ├── css/                  # Custom styling
│   │   └── custom.css       # Brand colors and overrides
│   └── theme/               # Theme customizations
│       └── BlogPostItem/    # Blog post footer component
│           └── Footer/
├── static/
│   ├── img/                 # Images and static assets
│   └── CNAME                # Custom domain (elroy.bot)
├── docusaurus.config.ts     # Main configuration
├── sidebars.ts             # Sidebar navigation
└── scripts/
    └── generate-html-files.js  # Post-build cleanup script
```

## URL Compatibility

All existing URLs from the MkDocs site are maintained:
- ✅ Docs: `/installation.html`, `/configuration/basic.html`, etc.
- ✅ Blog: `/blog/2025/07/07/autonomy-last.html` (matches canonical URLs)
- ✅ Root: Documentation served at site root

## Configuration Highlights

**`docusaurus.config.ts`:**
- `trailingSlash: false` - Maintains .html URLs
- `routeBasePath: '/'` for docs - Serves docs at site root
- Google Analytics: G-WGS6XZX78T
- Blog RSS feed: `/blog/rss.xml`

**`sidebars.ts`:**
- Mirrors original MkDocs navigation structure
- Configuration section with all subsections
- Tools section with guide and schema

## Deployment

The site is automatically deployed to GitHub Pages when changes are pushed to the `stable` branch via GitHub Actions (`.github/workflows/deploy-docs.yml`).

The deployment:
1. Checks out the repository
2. Sets up Node.js 20
3. Installs dependencies with `npm ci`
4. Builds the site with `npm run build`
5. Deploys `build/` directory to GitHub Pages
6. Maintains `elroy.bot` custom domain

## Styling

Custom CSS matches the original MkDocs Material theme:
- Primary colors: #B4B0CC, #C8C7E8
- Located in `src/css/custom.css`
- Blog post footer component at `src/theme/BlogPostItem/Footer/index.tsx`

## Contributing

When adding new documentation:

1. **Docs**: Place markdown files in `docs/` and update `sidebars.ts`
2. **Blog posts**: Add to `blog/` with format `YYYY-MM-DD-slug.md`
3. **Images**: Place in `static/img/` and reference as `/img/filename.png`
4. **MDX compatibility**: Ensure HTML tags are self-closing (e.g., `<img />`)

## Troubleshooting

### Build Errors

- **MDX errors**: All HTML tags must be properly closed (use `<img />` not `<img>`)
- **Image paths**: Use absolute paths from `/img/`
- **Broken links**: Verify all internal links reference existing files

### Development Server Issues

1. Delete `node_modules/` and `.docusaurus/`
2. Run `npm install`
3. Try `npm start` again

## Migration Details

This site was migrated from MkDocs. See `../DOCUSAURUS_MIGRATION.md` for:
- Complete migration checklist
- URL mapping details
- Configuration changes
- Files to remove after successful deployment

## Learn More

- [Docusaurus Documentation](https://docusaurus.io/docs)
- [Elroy Main Repository](https://github.com/elroy-bot/elroy)
- [Elroy Discord](https://discord.gg/5PJUY4eMce)
