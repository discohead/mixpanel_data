---
title: Segmentation Expressions
category:
  uri: Mixpanel APIs
content:
  excerpt: ''
privacy:
  view: public
---
Segmentation Expressions are used in [Query API](ref:query-api) and [Raw Data Export API](raw-data-export-api) to allow for more specificity when querying your data.

The power of segmentation comes from the ability to define custom expressions based on property names in the where and on parameters. An expression consists of a property, combined with one or more operators that can perform mathematical operations, logical operations, or typecasts. Expression are then applied in the where and on parameters of the segmentation API. The full grammar for expressions is given here:

```txt
<expression> ::= 'properties["' <property> '"]'
                | <expression> <binary op> <expression>
                | <unary op> <expression>
                | <math op> '(' <expression> ')'
                | <typecast op> '(' <expression> ')'
                | '(' <expression> ')'
                | <boolean literal>
                | <numeric literal>
                | <string literal>
  <binary op> ::= '+' | '-' | '*' | '/' | '%' | '==' | '!=' |
                  '>' | '>=' | '<' | '<=' | 'in' | 'and' | 'or'
   <unary op> ::= '-' | 'not'
    <math op> ::= 'floor' | 'round' | 'ceil'
<typecast op> ::= 'boolean' | 'number' | 'string'
   <property> ::= 'properties["' <property name> '"]'
```

## Examples

<Table align={["left","left"]}>
  <thead>
    <tr>
      <th>
        Expression
      </th>

      <th>
        Description
      </th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>
        `properties["account_id"] in [1,2,3,4]`
      </td>

      <td>
        Returns `true` if `account_id` event property is 1, 2, 3, or 4, otherwise `false`.
      </td>
    </tr>

    <tr>
      <td>
        `user["$email"] == "allison@example.com"`
      </td>

      <td>
        Returns `true` if `$email` user property is "[allison@example.com](mailto:allison@example.com)" otherwise `false`.
      </td>
    </tr>

    <tr>
      <td>
        `defined(properties["My Prop"])`
      </td>

      <td>
        Returns `true` if `My Prop` event property has any value, otherwise `false`. This is the same as "is set" in the UI.
      </td>
    </tr>

    <tr>
      <td>
        `not defined(properties["city"])`
      </td>

      <td>
        Returns `false` if `city` event property has any value, otherwise `true`. This is the same as "is not set" in the UI.
      </td>
    </tr>
  </tbody>
</Table>

## Typecast Operations

Internally, all properties of events have a type. This type is determined when we parse the event sent to us into a JSON object. Currently, there are three types, string, number, and boolean, which may be specified directly. A property may also have the values null and undefined, which are only handled internally. The default type is string. If you wish to treat an expression as another type, you may use the typecast operators to cast a property to a different type. For example, if `properties["signed up"]` has values of `"true"` and `"false"` as strings, and you wish to encode them as booleans, you may cast them by using the `boolean() typecast function: boolean(properties["signed up"])`.

The typecasting rules are described below.

## Casting to String

<Table align={["left","left"]}>
  <thead>
    <tr>
      <th>

      </th>

      <th>

      </th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>
        **Type**
      </td>

      <td>
        Result
      </td>
    </tr>

    <tr>
      <td>
        **String**
      </td>

      <td>
        Same String
      </td>
    </tr>

    <tr>
      <td>
        **Number**
      </td>

      <td>
        String containing the decimal representation of the number.
      </td>
    </tr>

    <tr>
      <td>
        **Boolean**
      </td>

      <td>
        "true" or "false"
      </td>
    </tr>

    <tr>
      <td>
        **null**
      </td>

      <td>
        null
      </td>
    </tr>

    <tr>
      <td>
        **Undefined**
      </td>

      <td>
        undefined
      </td>
    </tr>
  </tbody>
</Table>

## Casting to Number

<Table align={["left","left"]}>
  <thead>
    <tr>
      <th>

      </th>

      <th>

      </th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>
        **Type**
      </td>

      <td>
        Result
      </td>
    </tr>

    <tr>
      <td>
        **String**
      </td>

      <td>
        Attempts to interpret the string as a decimal. If this fails, the value becomes undefined.
      </td>
    </tr>

    <tr>
      <td>
        **Number**
      </td>

      <td>
        Same number
      </td>
    </tr>

    <tr>
      <td>
        **Boolean**
      </td>

      <td>
        1.0 if true, 0.0 if false
      </td>
    </tr>

    <tr>
      <td>
        **null**
      </td>

      <td>
        undefined
      </td>
    </tr>

    <tr>
      <td>
        **undefined**
      </td>

      <td>
        undefined
      </td>
    </tr>
  </tbody>
</Table>

## Binary Operations

The arithmetic operators `"-"`, `"*"`, `"/"`, `"%"` perform the subtraction, multiplication, division, and remainder operations, respectively. The division operator will return undefined if the divisor is 0. The sign of the value of the remainder will be equivalent to the dividend. All four of these operators expect both operands to be of the type number, or else the result is undefined.

The `"+"` operator behaves as addition if its two operands are of type number. However, if its two operands are of type string, it will concatenate the two strings. In other cases, the result is undefined.

The equals operator `"=="` will always return a boolean. When its two types are equal, it performs the standard equality comparison based on the values. If the types of its operands are not equal, false is returned. The not equals operator `"!="` returns false when the equals operator would return true and vice-versa.

The comparison operators `">"`, `">="`, `"<"`, and `"<="` returns a boolean value based on evaluating the comparison when its operands are both of type number. When its types are not equal, undefined is returned.

The `"in"` operator returns true if both operands are of type string and the first string is a substring of the second. When both operands are of differing types, undefined is returned.

The logical operators `"and"` and `"or"` accept boolean and undefined operands. An operand with type undefined evaluates as false. Any other types will result in an error.

## Unary and Math Operations

The `"-"` operator will negate an operand of type number, and return undefined otherwise.

The `"not"` operator will perform the logical not on an operand of type boolean. It will also evaluate an operand of type undefined as true. All other operands will be evaluated to undefined.

The `"floor"`, `"round"`, and `"ceil"` functions perform their mathematical operations on an operand of type number. On all other types, it will return undefined.
