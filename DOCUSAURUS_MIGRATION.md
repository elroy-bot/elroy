# Docusaurus Migration Summary

The documentation site has been successfully migrated from MkDocs to Docusaurus while maintaining all existing URLs.

## Key Changes

### Directory Structure
- **New location**: `website/` directory contains the complete Docusaurus site
- **Docs**: `website/docs/` (copied from `docs/`)
- **Blog**: `website/blog/` (migrated from `docs/blog/posts/`)
- **Static assets**: `website/static/img/` (copied from `docs/images/`)

### URL Compatibility
All existing URLs are maintained:
- ✅ `/installation.html` → works
- ✅ `/configuration/basic.html` → works
- ✅ `/blog/2025/07/07/autonomy-last.html` → works (matches canonical URLs)
- ✅ All doc pages generate `.html` files

### Configuration Highlights

**`website/docusaurus.config.ts`**:
- Site title, tagline, and URL configured for Elroy
- Google Analytics (G-WGS6XZX78T) integrated
- Blog RSS feed enabled
- Docs served at root (`routeBasePath: '/'`)
- `trailingSlash: false` to maintain .html URLs
- Client redirects plugin for backwards compatibility

**`website/sidebars.ts`**:
- Mirrors the original MkDocs navigation structure
- Configuration section with all subsections
- Tools section with guide and schema

### Styling
- Custom CSS in `website/src/css/custom.css` matches MkDocs Material theme colors (#B4B0CC, #C8C7E8)
- Blog post footer component added at `website/src/theme/BlogPostItem/Footer/index.tsx`

### Build Process
```bash
cd website
npm install
npm run build
```

The build includes a cleanup script that removes duplicate `.html.html` files created by the redirect plugin.

## Migration Checklist

- [x] Migrate all documentation pages
- [x] Migrate blog posts with proper dating
- [x] Copy all images and assets
- [x] Configure navigation/sidebar
- [x] Match styling to original site
- [x] Maintain .html URL structure
- [x] Configure Google Analytics
- [x] Add blog RSS feed
- [x] Test build successfully

## Deployment Updates

### GitHub Actions Workflow

The `.github/workflows/deploy-docs.yml` has been updated to:
- Use Node.js 20 instead of Python
- Run `npm ci` and `npm run build` in the `website/` directory
- Deploy the `website/build/` directory to GitHub Pages
- Maintain the `elroy.bot` CNAME

### Justfile Commands

Updated documentation commands:
```bash
just docs           # Start dev server (was: mkdocs serve)
just docs-build     # Build site (was: mkdocs build)
just docs-serve     # Serve built site locally (new)
just docs-deploy    # Info message about automatic deployment
```

## Next Steps

1. ✅ **Deployment updated**: GitHub Actions workflow modified for Docusaurus
2. ✅ **Justfile updated**: Commands now use npm instead of mkdocs
3. **Test locally**: Run `just docs` to start development server
4. **Test build**: Run `just docs-build` to ensure it builds correctly
5. **Deploy**: Push to `stable` branch to trigger automatic deployment
6. **Remove old files**: Once deployed successfully, remove:
   - `mkdocs.yml`
   - `overrides/` directory
   - MkDocs dependencies from Python requirements (mkdocs, mkdocs-material, etc.)

## Build Commands

```bash
# Development
cd website && npm start

# Production build
cd website && npm run build

# Serve built site locally
cd website && npm run serve
```

## Files to Keep/Remove

### Keep
- `docs/` - source markdown files (or migrate to `website/docs/`)
- All documentation content

### Can Remove (after successful deployment)
- `mkdocs.yml`
- `overrides/` directory
- MkDocs-related Python dependencies from requirements

## Blog Post Canonical URLs

All blog posts maintain their canonical URLs as specified in frontmatter:
- autonomy-last: `/blog/2025/07/07/add-autonomy-last.html`
- And all others match their date-based paths
