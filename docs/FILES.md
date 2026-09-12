# File storage contract

The file module accepts only bounded PDF, PNG, JPEG and WebP bytes with matching extension, MIME type and signatures. Its object-storage dependency is a protocol; the S3 adapter translates missing-object errors. Each file belongs to one user and receives an unguessable storage key. PostgreSQL tracks UPLOADING, READY, FAILED and EXPIRED states. An upload failure leaves a visible FAILED row; no customer endpoint exposes uploads yet.

`FILE_RETENTION_DAYS` (default 30) and `MAX_UPLOAD_BYTES` (default 20 MiB) are deployment settings, not product commitments. An hourly worker deletes objects past retention, then marks metadata EXPIRED. Object-storage failure rolls back metadata updates so cleanup can retry; periodic scanning limits batches to 100. Production object-store lifecycle policies should provide a second cleanup path, including interrupted uploads and orphaned objects.

Signatures are an initial gate only. Before customer uploads or service processing go live, add full format decoding, malware/active-content policy, decompression limits and isolated processors. Before delivering generated files, add authorization and signed access or streamed downloads. Current operations are internal and require a trusted caller.
