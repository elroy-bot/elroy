import React from 'react';
import Footer from '@theme-original/BlogPostItem/Footer';
import type FooterType from '@theme/BlogPostItem/Footer';
import type {WrapperProps} from '@docusaurus/types';

type Props = WrapperProps<typeof FooterType>;

export default function FooterWrapper(props: Props): JSX.Element {
  return (
    <>
      <Footer {...props} />
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
    </>
  );
}
