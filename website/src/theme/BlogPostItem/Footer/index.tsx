import React from 'react';
import Footer from '@theme-original/BlogPostItem/Footer';
import type FooterType from '@theme/BlogPostItem/Footer';
import type {WrapperProps} from '@docusaurus/types';
import {useBlogPost} from '@docusaurus/plugin-content-blog/client';
import {useLocation} from '@docusaurus/router';

type Props = WrapperProps<typeof FooterType>;

export default function FooterWrapper(props: Props): JSX.Element {
  const {metadata, isBlogPostPage} = useBlogPost();
  const location = useLocation();

  // Only show on individual blog post pages, not on blog list/index pages
  const showFooter = isBlogPostPage && location.pathname !== '/blog' && location.pathname !== '/blog/';

  return (
    <>
      <Footer {...props} />
      {showFooter && (
        <div className="blog-post-footer">
          <p>
            I'm an engineering manager and author of{' '}
            <a href="https://github.com/elroy-bot/elroy" target="_blank" rel="noopener">
              Elroy
            </a>
            , an AI memory assistant. <br />
            Get in touch at{' '}
            <a href="mailto:hello@elroy.bot">hello@elroy.bot</a> or on{' '}
            <a href="https://discord.gg/5PJUY4eMce">Discord</a>
          </p>
        </div>
      )}
    </>
  );
}
