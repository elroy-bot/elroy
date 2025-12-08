# Documentation

> **Note:** This directory contains the legacy MkDocs documentation. The site is now built with Docusaurus from the `website/` directory.
>
> **For documentation updates:** Edit files in `website/docs/` and `website/blog/` instead.
>
> The Docusaurus site maintains URL compatibility with the old MkDocs site - all existing URLs will continue to work.

## Migration Details

The documentation has been migrated to Docusaurus while maintaining complete URL compatibility:

- Documentation pages: `installation.html`, `cli.html`, etc. (same URLs as MkDocs)
- Blog posts: `/blog/YYYY/MM/DD/slug.html` format (same as MkDocs)
- All images and assets preserved

## Deployment

The Docusaurus site is automatically deployed via GitHub Actions on push to the `stable` branch.

See `.github/workflows/deploy-docs.yml` for deployment configuration.

## Local Development

To work on the documentation:

```bash
cd website
npm install
npm start  # Start development server
npm run build  # Build for production
```

## URL Compatibility

The Docusaurus configuration ensures all MkDocs URLs continue to work:

- `trailingSlash: false` - Generates clean URLs without trailing slashes
- `@docusaurus/plugin-client-redirects` - Creates `.html` redirects for all pages
- Custom build script removes duplicate `.html.html` files
