# Metodologia de cálculo do CPT do Espírito Santo

Este repositório prepara o cálculo do Coeficiente de Participação de Transição do Espírito Santo, seguindo a lógica do art. 115, §2º, I, da Lei Complementar nº 227/2026.

## Fórmula

Para cada ano `a`, de 2019 a 2026:

```text
ICMS_liq_ES_a = 0,75 * ICMS_bruto_ES_a
RPC_a = ICMS_liq_ES_a * Deflator_INPC_a
```

A Receita Média de Referência do Espírito Santo é:

```text
RME_ES = média simples de RPC_a, para a = 2019,...,2026
```

A Receita Bruta de Referência Nacional de 2026 é:

```text
RBR_2026 = ICMS_Brasil_2026 + ISS_Brasil_2026
```

O coeficiente é:

```text
CPT_ES = RME_ES / RBR_2026
```

## Estados da página

A página HTML foi preparada para exibir três situações.

**Cálculo final disponível**: quando houver dados completos de 2019 a 2026, incluindo RREO/Siconfi de 2026 e deflator INPC até dezembro de 2026.

**Estimativa preliminar**: quando houver dados parciais, por exemplo 2019 a 2025, permitindo uma aproximação, mas ainda sem o ano de 2026.

**Dados insuficientes**: quando a extração automática do Siconfi ainda não tiver produzido base bruta validável.

## Observação

O cálculo final depende da disponibilidade do RREO/Siconfi do 6º bimestre de 2026 e do INPC acumulado até dezembro de 2026. Antes disso, qualquer número deve ser tratado como estimativa preliminar.
