process SNIPPY_CORE {
    tag "$meta.id"
    label 'process_medium'

    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/snippy:4.6.0--hdfd78af_2':
        'quay.io/biocontainers/snippy:4.6.0--hdfd78af_2' }"

    input:
    tuple val(meta), path(vcf), path(aligned_fa)
    path reference

    output:
    tuple val(meta), path("${prefix}.aln")     , emit: aln
    tuple val(meta), path("${prefix}.full.aln"), emit: full_aln
    tuple val(meta), path("${prefix}.tab")     , emit: tab
    tuple val(meta), path("${prefix}.vcf")     , emit: vcf
    tuple val(meta), path("${prefix}.txt")     , emit: txt
    tuple val("${task.process}"), val('snippy-core'), eval("snippy-core --version 2>&1 | sed 's/snippy-core //'"), emit: versions_snippy_core, topic: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    prefix = task.ext.prefix ?: "${meta.id}"
    def is_compressed = reference.getName().endsWith(".gz") ? true : false
    def reference_name = reference.getName().replace(".gz", "")
    """
    if [ "$is_compressed" == "true" ]; then
        gzip -c -d $reference > $reference_name
    fi

    # Collect samples into necessary folders
    mkdir samples
    find . -name "*.vcf" | sed 's/\\.vcf\$//' | xargs -I {} bash -c 'mkdir samples/{}'
    find . -name "*.vcf" | sed 's/\\.vcf\$//' | xargs -I {} bash -c 'cp -L {}.vcf samples/{}/{}.vcf'
    find . -name "*.aligned.fa" | sed 's/\\.aligned.fa\$//' | xargs -I {} bash -c 'cp -L {}.aligned.fa samples/{}/{}.aligned.fa'

    # Run snippy-core. It exits non-zero when snp-sites finds no variant sites
    # (identical samples), leaving no core.aln. Only in that case, write a zero-length
    # core alignment so snp-dists reports all-zero distances; any other failure fails.
    set +e
    snippy-core \\
        $args \\
        --ref $reference_name \\
        --prefix $prefix \\
        samples/* 2>&1 | tee snippy-core.log
    status=\${PIPESTATUS[0]}
    set -e
    if [ \$status -ne 0 ]; then
        if grep -q "No SNPs were detected" snippy-core.log && [ -s ${prefix}.full.aln ]; then
            awk '/^>/{print; print ""}' ${prefix}.full.aln > ${prefix}.aln
        else
            exit \$status
        fi
    fi
    """

    stub:
    prefix = task.ext.prefix ?: "${meta.id}"
    """
    mkdir samples/
    touch ${prefix}.aln
    touch ${prefix}.full.aln
    touch ${prefix}.tab
    touch ${prefix}.vcf
    touch ${prefix}.txt
    """
}
