import type { AppProps } from "next/app";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <style jsx global>{`
        html,
        body,
        #__next {
          height: 100%;
          margin: 0;
        }
      `}</style>
      <Component {...pageProps} />
    </>
  );
}
