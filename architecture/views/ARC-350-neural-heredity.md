# ARC-350 — Model-Independent Neural Heredity

**Status:** REVIEWED  
**Gate:** N0  
**Freeze state:** IMPLEMENTATION-READY  
**Change class:** Future architecture/domain-contract refinement  
**Question:** Which genetic laws and adapter boundaries permit neural heredity without changing EXP-000 or allowing evaluation to become reproductive causality?

## Scope and non-scope

This view owns the model-independent neural-heredity laws for a later experiment.
It does not enable neural heredity, within-life parameter learning, resource
mechanics, cross-architecture reproduction, or population evolution. EXP-000
continues to use `NullGenome` exactly as owned by LC-220.

The first neural-heredity study remains a homogeneous population with one exact
founder checkpoint, identical Generation-0 effective neural state, no assigned
personality, no initial neural diversity, no resource pressure, no causal
physical space, and autonomous bilateral mate choice.

The primary founder candidate is `allenai/OLMo-2-0425-1B-Instruct`. It is a
candidate, not an admitted or frozen founder. Candidate failure changes only
the admission candidate, never this architecture.

## Causal authority

```text
Agent cognition
    -> REPRODUCTION_PROPOSE
    -> REPRODUCTION_ACCEPT
    -> ReproductionService validates world eligibility
    -> BirthPlan
    -> GenomeInheritance
    -> ChildGenome artifact
    -> P11 atomic birth + lineage + genome_ref commit
```

`GenomeInheritance` is a deterministic construction service. Its complete
authority is:

```text
eligible selected parent genomes
+ manifest-pinned inheritance law
+ deterministic genome RNG
-> child genome
```

It cannot select or rank parents, calculate reproductive fitness, inspect
benchmark results, inspect researcher phenotype or relationship scores, inspect
private non-visible agent state, alter reproduction probability, or override an
agent's mate choice. Parent proposal and acceptance roles remain reproduction
event metadata and cannot change genetic contribution.

## Genome domain

The model-independent hierarchy is:

```text
Genome
|-- NullGenome
|-- AdapterGenome
|-- MetaGenome       (future)
`-- WeightGenome     (future)
```

N0 admits only `NullGenome` and `AdapterGenome`. The exact field and validation
authority is
[`genome.schema.yaml`](../../specs/domain/genome.schema.yaml).

`NullGenome` means neural heredity is disabled. `ZERO_ADAPTER` is an
`AdapterGenome` sentinel meaning neural heredity is enabled while the effective
delta is zero. They are not aliases and never share a semantic discriminator.
Behavior, personality, relationship, benchmark, social-rank, and trust labels
are forbidden genome fields.

## Founder genome

Generation-0 neural-heredity founders use the shared `ZERO_ADAPTER` sentinel:

```text
W_agent = W_base + delta_W
delta_W = 0
```

The sentinel is bound to the immutable base digest, architecture signature,
tokenizer digest, adapter schema, target modules, rank, scaling metadata, and
canonical tensor codec. Its canonical digest and zero
`effective_delta_digest` are deterministic. It has no physical tensor artifact
until the backend must materialize one. Materialization must reproduce the same
zero effective-delta digest. Implementations must not create one redundant zero
adapter per founder.

## Scientific and execution representations

Authority order:

```text
official immutable BF16/open base checkpoint
+ canonical AdapterGenome
-> effective agent neural state
```

The canonical genotype is the separate, canonical PEFT/PyTorch LoRA factor
state plus the identity of the effective neural delta it realizes. The base is
immutable and is never merged into canonical genome storage.
`merge_and_unload()` output is therefore not a canonical genome.

The storage genotype consists of ordered LoRA factors `A` and `B`. For each
target module:

```text
effective_delta = scale * B @ A
```

The effective genotype is the canonically ordered set of reconstructed
`effective_delta` tensors. Arbitrary equivalent LoRA factor coordinates are not
treated as biologically meaningful coordinates. H1, H2, and M1 laws operate on
effective deltas, not directly on factors.

The runtime representation is a derived llama.cpp GGUF LoRA artifact. GGUF
base and adapter files are execution artifacts only: no mutation or crossover
operates on quantized GGUF weights. Each derived runtime artifact records the
source canonical genome digest, converter identity/version, conversion-policy
version, and output digest. It is disposable and regenerable.

## N0 effective-delta codec

`ALIFELM_EFFECTIVE_DELTA_V1` fixes these rules:

- canonical module paths are the architecture-signature paths selected by the
  manifest; paths are unique and sorted by unsigned UTF-8 byte order;
- a module contributes one two-dimensional weight delta in `[out, in]` order;
- effective keys are `effective::<module_path>::weight`;
- storage keys are `adapter::<module_path>::lora_A.weight` and
  `adapter::<module_path>::lora_B.weight`;
- `A` has shape `[rank, in]`, `B` has shape `[out, rank]`, and the declared
  scale is applied exactly once when reconstructing the effective delta;
- canonical factor and effective-delta payloads are contiguous, little-endian
  IEEE-754 binary32; construction may use binary64 intermediates only in the
  pinned reference backend and rounds once to binary32 at the codec boundary;
- tensor identity bytes are length-prefixed key bytes, dtype, rank, dimensions,
  and raw row-major bytes in canonical module/key order;
- SHA-256 over those identity bytes is the effective-delta digest;
- the factor artifact is one uncompressed safetensors payload, with tensor keys
  supplied in canonical order, no user metadata, and SHA-256 CAS identity;
- factor scaling is normalized into the schema's ordered scaling records before
  state hashing; backend-specific key prefixes and adapter names are excluded;
- the N0 rank policy is `FIXED_MANIFEST_RANK`; all C0 parents use the same
  adapter schema/rank and every child is projected to that rank.

The operator first constructs an ideal effective target. The reference codec
then uses a deterministic truncated factorization and reconstructs the actual
child effective delta from the emitted factors. The child digest and distance
metrics describe this reconstructed delta; evidence also records target norm,
reconstruction residual, discarded singular-value norm, and changed-parameter
count. An implementation must not report the pre-factorization target as the
realized child state.

For nonzero targets, N0 uses balanced truncated SVD:

```text
target ~= U_r * S_r * Vh_r
A = sqrt(S_r) * Vh_r
B = U_r * sqrt(S_r) / scale
```

For each component, the largest-absolute entry in the `U` column is selected,
with the lowest row index breaking a tie; `U` and the matching `Vh` row are
jointly sign-flipped so that entry is non-negative. Degenerate subspace and
math-library behavior is owned by one manifest-pinned
`N0_REFERENCE_GENOME_CONSTRUCTION_BACKEND`. Canonical child construction is
authoritative only on that exact backend identity/version/environment digest.
No cross-CPU/GPU or cross-platform bit-identity claim is made. Other devices
may execute a verified canonical artifact but may not silently construct a
different canonical child under the same identity.

## Compatibility law

Compatibility derives from tensor identity, not a human-readable model family:

| Class | Rule | N0 result |
|---|---|---|
| `C0_EXACT_BASE` | Same base digest, architecture signature, tokenizer digest, adapter schema, rank/scaling convention, and ordered target modules | Direct N0 inheritance allowed |
| `C1_COMPATIBLE_TOPOLOGY` | Structurally compatible but base/checkpoint digest differs | Future research; reject in N0 |
| `C2_CROSS_ARCHITECTURE` | Neural topology or tensor contract is incompatible | Direct crossover forbidden |

All non-C0 cases fail closed before RNG consumption or child artifact creation.
No projection, name-based matching, padding, truncation, or partial-module merge
is an implicit fallback.

## Operator contract and registry

The exact machine contract is
[`inheritance-operator.schema.yaml`](../../specs/protocol/inheritance-operator.schema.yaml).
The domain operation is:

```text
InheritanceOperator.apply(
    parent_a,
    parent_b,
    operator_spec,
    deterministic_rng,
) -> InheritanceResult
```

`InheritanceResult` contains the child genome, operator evidence, operator
metrics, and canonical artifact references. For symmetric operators, inputs are
canonicalized by ascending `(effective_delta_digest, canonical_artifact_digest,
genome_id)` before any mask or contribution is evaluated. Consequently:

```text
inherit(A, B, seed) == inherit(B, A, seed)
```

at the realized effective-genotype level for an operator declared symmetric.

N0 registry laws are treatments, not ranked algorithms:

- `H0_NULL`: heredity is disabled; the module-off control child has
  `NullGenome`. H0_NULL is not mixed with H1/H2 parent pools. Evidence uses SHA-256
  of the canonical `NullGenome` singleton descriptor as its genome/artifact
  identity, a null artifact reference, and the zero-effective-state digest;
  this does not make `NullGenome` a zero adapter.
- `H0_RESET_ZERO`: heredity pipeline sham control. A successful birth invokes
  `GenomeInheritance`, ignores both parental neural deltas, applies no mutation,
  and assigns a canonical base-bound `ZERO_ADAPTER` child with realized
  effective delta zero under the same immutable base/runtime semantics. It is a
  control treatment, not a biological inheritance claim.
- `H1_SYMMETRIC_DELTA_BLEND`: ideal target is
  `0.5 * delta_A + 0.5 * delta_B`; alpha is exactly `0.5` and is not optimized.
- `H2_RANDOM_DELTA_CROSSOVER`: N0 freezes `MODULE` mask granularity and a
  manifest-pinned `0.5` choice probability. One deterministic mask bit selects
  all effective tensors of a target module from canonical parent 0 or parent 1.
- `M1_SPARSE_GAUSSIAN_MUTATION`: before factorization, add an element mask with
  probability `p` times deterministic `Normal(0, sigma)` noise. `p` and `sigma`
  are canonical decimal strings pinned by the ExperimentManifest. `p=0`
  consumes no mutation-noise values and preserves the unmutated target.

TIES, DARE, BLX-alpha, SVD merge variants other than the codec projection,
magnitude pruning, and full `WeightGenome` operations remain future
experimental treatments. They are not N0 baselines.

H1 and H2 remain separate treatments if both pass admission. N0 evaluates only
contract validity, determinism, symmetry, reproducibility, artifact integrity,
loadability, and minimum organism viability. Benchmark, intelligence, social,
reproduction-rate, language-quality, and researcher-preference rankings cannot
select an operator.

## Genome RNG

`ALIFELM_GENOME_RNG_V1` uses HKDF-SHA-256. Input records use the repository's
canonical UTF-8 JSON rule: sorted object keys, no insignificant whitespace,
ordered arrays, and canonical decimal strings for non-integral numbers.

The master input contains:

- `root_seed` as an exact manifest byte string;
- `replication_id`;
- `child_birth_seq`;
- sorted parent genome digests;
- `genome_policy_version`;
- inheritance operator ID/version;
- mutation operator ID/version.

The salt is SHA-256 of UTF-8 `A-LifeLM/GENOME_RNG/V1`; HKDF info is the
canonical input record excluding `root_seed`, and the input key material is the
exact `root_seed` bytes. The derivation digest is SHA-256 of the complete
canonical input record. Each stream key is HKDF-expanded with exactly one of:

```text
GENOME_CROSSOVER
GENOME_MUTATION_MASK
GENOME_MUTATION_NOISE
GENOME_DECOMPOSITION
```

Counter blocks are HMAC-SHA-256 under the stream key over the stream label plus
an unsigned 128-bit big-endian counter. Mask sampling compares the next
unsigned 64-bit word with the exact fixed-point threshold derived from the
manifest decimal probability. `REFERENCE_BACKEND_NORMAL_V1` consumes two
unsigned 64-bit words, maps each to the open interval by
`u = (word + 0.5) / 2^64`, and applies Box-Muller in pairs using the pinned
binary64 math implementation before the codec's binary32 rounding. Gaussian
mapping and decomposition tie behavior are versioned parts of the pinned
reference construction backend; no cross-platform bit identity is claimed
outside that backend.

Global Python, NumPy, or Torch RNG state, UUID randomness, wall time, thread or
completion order, retry count, and process-local entropy are forbidden. A retry
with the same causal inputs reconstructs the same genome identity, factors,
evidence, and CAS bytes.

## Backend boundary

The domain depends on `AdapterGenomeBackend`, never on PEFT classes. The primary
implementation is `PEFTAdapterBackend`, responsible for:

- zero-adapter creation/materialization;
- adapter load and schema validation;
- deterministic normalized-state extraction;
- effective-delta calculation;
- reference factorization and child-adapter creation;
- canonical save, reload, and digest/effective-delta verification;
- active-genome switching over one shared immutable base;
- confirmation that base parameters never changed.

Backend isolation admission must run `A -> inference`, `B -> inference`, then
`A -> inference`; with identical context, seed, genome A, and pinned runtime
determinism contract, both A executions must match. Adapter state, KV/cache
state, and backend naming must not bleed between genomes.

## Persistence and crash law

The authoritative ordering is owned by
[`SEQ-351`](SEQ-351-genome-artifact-commit.md). Canonical adapter blobs remain
in CAS; SQLite/WAL remains canonical materialized-state/event/metadata storage.
Large tensor payloads are never duplicated into SQLite.

A precommit CAS artifact may be orphaned. A committed child may never reference
a missing, staged, or digest-mismatched required genome artifact. Retry resolves
the deterministic birth/genome/commit identity and returns the existing result
or reconstructs the identical artifact; it cannot allocate a different genome.

## Genome events, evidence, and analysis

Versioned event types are `GenomeFounderAssigned`, `GenomeInherited`,
`GenomeMutated`, and `GenomeRuntimeArtifactDerived`. Every genome event is
`RESEARCHER_ONLY`. N0 records mutation metadata inside the causal
`GenomeInherited` record; it does not also emit `GenomeMutated` for the same
birth. The separate mutation event is reserved for a future mutation-only
transition. Runtime derivation never mutates the canonical genome.

Exact evidence fields are owned by
[`genome-evidence.schema.yaml`](../../specs/protocol/genome-evidence.schema.yaml).
Evidence is a deterministic reconstruction recipe and integrity record, not a
duplicate tensor payload. Reconstruction requires the referenced parent/base
artifacts, manifest/root seed, operator specs, and pinned reference backend.

L1 distance, L2 distance, cosine similarity, relative delta norm, per-layer or
per-module norms, and parameter-change density are Observatory/analysis values.
They cannot affect mate choice, survival, birth eligibility, reproduction,
ContextPack, resources, or canonical genetic construction.

Heredity evidence may support reproductive genealogy, neural phylogeny,
genotype-distance views, mutation timelines, and founder-to-descendant tracing.
Those views remain separate from relationship graphs, behavioral phenotype,
and cultural-transmission graphs. Analysis/export schemas may attach column
metadata (`description`, `logical_type`, `analysis_role`, `unit`,
`enum_values`, `tags`) and derive Parquet, DuckDB, or JSONL products. SQLite/CAS
remain canonical.

## Genome, memory, culture, and lineage firewall

```text
GENOME  = neural parameters
MEMORY  = individual event-derived visible history
CULTURE = information transmitted through world channels
LINEAGE = researcher-side ancestry metadata
```

A child never automatically receives parent transcript, summary, private
history, personality or phenotype labels, relationship metrics, lineage facts,
or benchmark scores. Genome events, seeds, distances, ancestry, and analysis
labels do not enter ContextPack. Future cultural inheritance requires an
explicit, separate experimental treatment and visible transmission path.

Future axes remain orthogonal and manifest-pinned: `DARWINIAN` birth-time
variation, `LAMARCKIAN` acquired-adapter inheritance, `CULTURE_ONLY`,
`GENETIC_ONLY`, and `HYBRID`. N0 is Darwinian only and has no within-life
parameter learning.

Resource interventions are also a separate causal axis. N0 implements none.
Future `NO_RESOURCE`, `PLACEBO_OBJECT`, `HIDDEN_BENEFICIAL_RESOURCE`,
`SCARCITY`, `RENEWABLE_RESOURCE`, and `TRANSFERABLE_RESOURCE` treatments must
be separately pinned and evidenced; no food, money, medicine, or fitness
semantics enter N0.

## Founder model action boundary

`ModelActionInterface` supports `NATIVE_TOOL`, `CONSTRAINED_JSON`, and
`GRAMMAR_STRUCTURED`. Each transport normalizes to the same canonical
`ActionIntent` before existing validation. Native tool/function calling is not
an architecture requirement, and the transport cannot add social-desirability
or mate-preference semantics.

Founder authority is an official immutable open BF16 checkpoint. A llama.cpp
GGUF, initially Q8_0 for the OLMo candidate, is only a runtime candidate.

Admission occurs separately and in order:

```text
C0 Killer Gate (10 probes)
  factual >= 9/10
  structural/reference valid = 10/10
  malformed = 0
-> C20
-> Motor
-> Autonomous
-> founder checkpoint freeze
```

C0 is a pre-screen. Its ten probes require factual accuracy at least 9/10,
reference/structure validity 10/10, and zero malformed outputs. Full C20
admission additionally requires overall factual accuracy at least 90% and
`CRITICAL_CORE_ACCURACY = 100%`. Critical-core probes cover self identity, peer
identity/reference, target reference, incoming and outgoing proposal ownership,
proposal direction, proposal target, and reproduction/proposal handle
grounding. Any critical-core error fails founder admission regardless of the
aggregate score.

These are comprehension and grounding gates only. `MESSAGE_RECEIVED` does not
imply SEND, and `PROPOSAL_RECEIVED` does not imply ACCEPT or REJECT. Admission
must not prescribe a behavioral response. Exact field authority is
[`founder-model-admission.yaml`](../../specs/experiments/founder-model-admission.yaml).

If OLMo fails, test `VillanovaAI/Villanova-2B-2603`, then
`YuLan-Mini-Instruct 2.4B`; the heredity contracts do not change.

After Founder Freeze, baseline and heredity work branch independently. M2 first
resolves remaining baseline blockers, then uses EXP-000 `NullGenome` and proceeds
to headless EXP-000 baseline validation; N0 is not an M2 prerequisite. In the
separate branch, H0_RESET_ZERO/H1/H2 and the backend complete bounded N0
admission. A neural-heredity experiment requires both the validated headless
baseline and an admitted N0 operator/backend, with exact base/tokenizer,
PEFT/reference backend, operator/mutation policy, and PEFT-to-GGUF converter
identities frozen in its ExperimentManifest.

## External boundaries and N0 admission

External dependency decisions and rationale are owned by
[`ADR-350-003`](../decisions/ADR-350-003-external-genetics-dependencies.md).
The bounded operator admission protocol and complete future test-ID catalog are
owned by
[`N0-heredity-operator-admission.yaml`](../../specs/experiments/N0-heredity-operator-admission.yaml).
Viability probes test compact-context comprehension and Motor action validity
only; they are pass/fail minimum functionality checks and never fitness.
H0_RESET_ZERO additionally must match base/zero-adapter inference behavior for
identical context and seed under the pinned backend determinism contract.

## Owner boundaries

- A00 retains foundation invariants.
- LC-220 retains autonomous bilateral parent selection and EXP-000
  `NullGenome` child semantics.
- ARC-240 retains State/Event/Artifact/Protocol classification.
- ARC-270 retains CAS-before-reference and atomic durable commit semantics.
- ARC-300 retains ContextPack visibility; genome/evidence/phenotype stay hidden.
- This view owns neural-heredity semantic law and the genetic/cultural firewall.
- Machine schemas own exact fields; SEQ-351 owns child-genome commit ordering;
  ADRs own decision rationale; the N0 admission spec owns admission cases.

EXP-000 domain types, kernel behavior, persistence behavior, action semantics,
and causal outputs are unchanged by this architecture finalization.
