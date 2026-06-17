/** Download buttons for files returned by the assistant (presigned URLs). */
export default function Files({ files }) {
  return (
    <div className="files">
      <div className="files__title">Файлы:</div>
      {files.map((url, idx) => (
        <a
          key={idx}
          className="file-button"
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          download=""
        >
          Скачать файл {idx + 1}
        </a>
      ))}
    </div>
  );
}
