/**
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React, {type ReactNode, useCallback, useMemo, useState} from 'react';
import clsx from 'clsx';
import {useLocation} from '@docusaurus/router';
import {prefersReducedMotion, ThemeClassNames} from '@docusaurus/theme-common';
import Layout from '@theme/Layout';
import DocSidebar from '@theme/DocSidebar';

import type {Props} from '@theme/BlogLayout';
import type {PropSidebarItem} from '@docusaurus/plugin-content-docs';

import styles from './styles.module.css';

function useDocsSidebarItems(): PropSidebarItem[] | null {
  return useMemo(() => {
    try {
      // Load the generated docs props JSON that contains fully-resolved sidebar items.
      const ctx = require.context(
        '@generated/docusaurus-plugin-content-docs/default/p',
        false,
        /index-.*\\.json$/,
      );
      const module = ctx(ctx.keys()[0]) as {
        version?: {docsSidebars?: {docs?: PropSidebarItem[]}};
      };
      return module?.version?.docsSidebars?.docs ?? null;
    } catch {
      return null;
    }
  }, []);
}

export default function BlogLayout({
  toc,
  children,
  ...layoutProps
}: Props): ReactNode {
  const sidebarItems = useDocsSidebarItems();
  const hasSidebar = sidebarItems && sidebarItems.length > 0;
  const {pathname} = useLocation();
  const [hiddenSidebarContainer, setHiddenSidebarContainer] = useState(false);
  const [hiddenSidebar, setHiddenSidebar] = useState(false);

  const toggleSidebar = useCallback(() => {
    if (hiddenSidebar) {
      setHiddenSidebar(false);
    }
    if (!hiddenSidebar && prefersReducedMotion()) {
      setHiddenSidebar(true);
    }
    setHiddenSidebarContainer((value) => !value);
  }, [hiddenSidebar]);

  return (
    <Layout {...layoutProps}>
      <div className={styles.layout}>
        {hasSidebar && (
          <aside
            className={clsx(
              ThemeClassNames.docs.docSidebarContainer,
              styles.sidebarContainer,
              hiddenSidebarContainer && styles.sidebarContainerHidden,
            )}
            onTransitionEnd={(e) => {
              if (!e.currentTarget.classList.contains(styles.sidebarContainer)) {
                return;
              }
              if (hiddenSidebarContainer) {
                setHiddenSidebar(true);
              }
            }}>
            <div
              className={clsx(
                styles.sidebarViewport,
                hiddenSidebar && styles.sidebarViewportHidden,
              )}>
              <DocSidebar
                path={pathname}
                sidebar={sidebarItems}
                onCollapse={toggleSidebar}
                isHidden={hiddenSidebar}
              />
            </div>
          </aside>
        )}
        <main className={styles.main}>
          <div className="container margin-vert--lg">
            <div className="row">
              <div
                className={clsx('col', {
                  'col--7': Boolean(toc),
                  'col--9 col--offset-1': !toc,
                })}>
                {children}
              </div>
              {toc && <div className="col col--2">{toc}</div>}
            </div>
          </div>
        </main>
      </div>
    </Layout>
  );
}
