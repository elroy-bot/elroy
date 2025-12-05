# Docusaurus Deployment Checklist

This checklist guides you through deploying the new Docusaurus documentation site.

## Pre-Deployment Testing

- [ ] **Local build test**
  ```bash
  cd website
  npm install
  npm run build
  ```
  Verify: Build completes without errors

- [ ] **Local server test**
  ```bash
  npm run serve
  ```
  Verify: Site loads at http://localhost:3000 and all pages render correctly

- [ ] **URL verification**
  Check these URLs work locally:
  - [ ] http://localhost:3000/installation.html
  - [ ] http://localhost:3000/configuration/basic.html
  - [ ] http://localhost:3000/blog/2025/07/07/autonomy-last.html
  - [ ] http://localhost:3000/blog (blog index)
  - [ ] http://localhost:3000/ (home page)

- [ ] **Navigation test**
  - [ ] Sidebar navigation works
  - [ ] Top navbar links work
  - [ ] Blog post links work
  - [ ] Image assets load correctly

## Deployment Steps

### 1. Commit Changes

```bash
git add .
git commit -m "Migrate documentation from MkDocs to Docusaurus"
```

### 2. Test on Non-Production Branch (Optional)

```bash
# Create a test branch
git checkout -b test-docusaurus-deploy

# Push to test branch
git push origin test-docusaurus-deploy

# Temporarily update .github/workflows/deploy-docs.yml to trigger on test branch
# Test the deployment, then revert changes
```

### 3. Deploy to Production

```bash
# Merge to stable branch (triggers automatic deployment)
git checkout stable
git merge main  # or your feature branch
git push origin stable
```

### 4. Monitor GitHub Actions

1. Go to: https://github.com/elroy-bot/elroy/actions
2. Watch the "Deploy Docs" workflow
3. Verify: Workflow completes successfully
4. Check: GitHub Pages deployment status

### 5. Verify Live Site

- [ ] Visit https://elroy.bot
- [ ] Check key URLs:
  - [ ] https://elroy.bot/installation.html
  - [ ] https://elroy.bot/configuration/basic.html
  - [ ] https://elroy.bot/blog/2025/07/07/autonomy-last.html
  - [ ] https://elroy.bot/blog
- [ ] Verify Google Analytics tracking (check GA dashboard)
- [ ] Test RSS feed: https://elroy.bot/blog/rss.xml
- [ ] Check mobile responsiveness
- [ ] Test dark/light theme toggle

## Post-Deployment

### Cleanup Old Files

Once the site is verified working:

- [ ] **Remove MkDocs files**
  ```bash
  rm mkdocs.yml
  rm -rf overrides/
  ```

- [ ] **Update Python dependencies**
  Remove from requirements or pyproject.toml:
  - mkdocs
  - mkdocs-material
  - mkdocs-get-deps
  - mkdocs-macros-plugin
  - mkdocs-rss-plugin
  - mkdocs-git-revision-date-localized-plugin
  - Any other mkdocs-* packages

- [ ] **Update documentation references**
  - [ ] Update CONTRIBUTING.md if it references MkDocs
  - [ ] Update any developer guides
  - [ ] Update CI/CD documentation

- [ ] **Commit cleanup**
  ```bash
  git add .
  git commit -m "Remove MkDocs configuration and dependencies"
  git push origin stable
  ```

### Monitor

- [ ] Check Google Analytics for traffic
- [ ] Monitor GitHub Issues for broken link reports
- [ ] Check search engine indexing (Google Search Console)
- [ ] Verify RSS feed subscribers still receive updates

## Rollback Plan

If issues occur after deployment:

### Quick Rollback

1. **Revert the workflow file:**
   ```bash
   git checkout stable
   git revert <commit-hash-of-docusaurus-changes>
   git push origin stable
   ```

2. **Emergency: Use old MkDocs site**
   - Checkout a commit before the migration
   - Deploy manually: `mkdocs gh-deploy --force`

### Issues and Solutions

| Issue | Solution |
|-------|----------|
| URLs not working | Check CNAME file in `website/static/CNAME` |
| Images not loading | Verify images in `website/static/img/` |
| Blog posts missing | Check blog files in `website/blog/` |
| Build fails | Review GitHub Actions logs, check local build |
| Analytics not tracking | Verify GA tracking ID in `docusaurus.config.ts` |

## Support

- Review `DOCUSAURUS_MIGRATION.md` for detailed changes
- Review `website/README.md` for site-specific documentation
- Check Docusaurus docs: https://docusaurus.io/docs

## Success Criteria

✅ Deployment is successful when:

1. All URLs from old site work on new site
2. Google Analytics tracking works
3. RSS feed delivers updates
4. No broken links or images
5. Mobile and desktop views work correctly
6. Blog posts display correctly with proper dates
7. Search functionality works (if enabled)
8. GitHub Actions workflow runs without errors

---

**Deployed by:** _____________
**Date:** _____________
**Verified by:** _____________
**Issues encountered:** _____________
